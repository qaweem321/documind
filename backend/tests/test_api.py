from fastapi.testclient import TestClient

from .conftest import FakeAnswerer, make_pdf, parse_sse, upload, wait_until_processed

HANDBOOK = b"""# Equipment Policy

Laptops are company property and must be returned within 10 business days after your last day.

## Home office

New employees receive a home office budget of 1500 dollars for a desk and chair.
"""

TRAVEL = b"""# Travel Policy

Hotels should cost no more than 250 dollars a night. Economy class is the default for flights.
"""


def ask(client: TestClient, conversation_id: str, content: str) -> list[tuple[str, object]]:
    response = client.post(f"/api/conversations/{conversation_id}/messages", json={"content": content})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


def test_upload_processes_markdown_into_chunks(client: TestClient) -> None:
    result = upload(client, "equipment.md", HANDBOOK)
    assert result["document"]["status"] == "processing"
    document = wait_until_processed(client, result["document"]["id"])
    assert document["status"] == "ready"
    assert document["title"] == "Equipment Policy"
    assert document["chunkCount"] >= 1


def test_pdf_chunks_keep_page_numbers(client: TestClient) -> None:
    pdf = make_pdf(
        ["Vacation days carry over until March.", "Sick leave needs a doctor note after three days."]
    )
    document = wait_until_processed(client, upload(client, "leave.pdf", pdf)["document"]["id"])
    assert document["pageCount"] == 2
    results = client.post("/api/search", json={"query": "doctor note sick leave"}).json()
    assert results[0]["page"] == 2


def test_duplicate_and_invalid_uploads_are_reported_per_file(client: TestClient) -> None:
    first = upload(client, "equipment.md", HANDBOOK)
    response = client.post(
        "/api/documents",
        files=[
            ("files", ("copy.md", HANDBOOK)),
            ("files", ("fake.pdf", b"not a pdf")),
            ("files", ("x.exe", b"MZ")),
        ],
    )
    copy, fake, exe = response.json()
    assert copy["duplicate"] is True and copy["document"]["id"] == first["document"]["id"]
    assert "isn't a PDF" in fake["error"]
    assert "isn't supported" in exe["error"]


def test_hybrid_search_finds_the_right_passage_and_respects_the_document_filter(client: TestClient) -> None:
    equipment = wait_until_processed(client, upload(client, "equipment.md", HANDBOOK)["document"]["id"])
    travel = wait_until_processed(client, upload(client, "travel.md", TRAVEL)["document"]["id"])
    results = client.post("/api/search", json={"query": "How much can a hotel cost per night?"}).json()
    assert results[0]["documentId"] == travel["id"]
    assert "250 dollars" in results[0]["content"]
    filtered = client.post(
        "/api/search", json={"query": "hotel cost per night", "documentIds": [equipment["id"]]}
    ).json()
    assert {r["documentId"] for r in filtered} == {equipment["id"]}


def test_chat_streams_sources_text_citations_and_saves_the_answer(
    client: TestClient, answerer: FakeAnswerer
) -> None:
    wait_until_processed(client, upload(client, "equipment.md", HANDBOOK)["document"]["id"])
    conversation = client.post("/api/conversations", json={}).json()
    assert conversation["title"] == "New chat"

    events = ask(client, conversation["id"], "When do I return my laptop?")
    names = [name for name, _ in events]
    assert names[0] == "sources" and names[-1] == "done"
    assert "citation" in names
    sources = events[0][1]
    assert isinstance(sources, list) and "Laptops" in sources[0]["content"]

    saved = client.get(f"/api/conversations/{conversation['id']}").json()
    assert saved["title"] == "When do I return my laptop?"
    user, assistant = saved["messages"]
    assert user["content"] == "When do I return my laptop?"
    assert assistant["content"] == "Answer: it's in the documents."
    assert assistant["segments"][1]["citations"][0]["sourceIndex"] == 0
    assert assistant["sources"][0]["documentTitle"] == "Equipment Policy"


def test_follow_ups_send_history_and_search_with_the_previous_question(
    client: TestClient, answerer: FakeAnswerer
) -> None:
    wait_until_processed(client, upload(client, "travel.md", TRAVEL)["document"]["id"])
    conversation = client.post("/api/conversations", json={}).json()
    ask(client, conversation["id"], "What is the hotel limit?")
    ask(client, conversation["id"], "And for flights?")
    question, history, _ = answerer.calls[-1]
    assert question == "And for flights?"
    assert [t.role for t in history] == ["user", "assistant"]
    assert history[0].content == "What is the hotel limit?"


def test_conversation_document_filter_limits_the_sources(client: TestClient) -> None:
    equipment = wait_until_processed(client, upload(client, "equipment.md", HANDBOOK)["document"]["id"])
    wait_until_processed(client, upload(client, "travel.md", TRAVEL)["document"]["id"])
    conversation = client.post("/api/conversations", json={"documentIds": [equipment["id"]]}).json()
    sources = ask(client, conversation["id"], "hotel cost")[0][1]
    assert isinstance(sources, list)
    assert {s["documentId"] for s in sources} == {equipment["id"]}


def test_deleting_a_document_removes_its_chunks_from_search(client: TestClient) -> None:
    document = wait_until_processed(client, upload(client, "travel.md", TRAVEL)["document"]["id"])
    assert client.delete(f"/api/documents/{document['id']}").status_code == 204
    assert client.post("/api/search", json={"query": "hotel"}).json() == []
    assert client.delete(f"/api/documents/{document['id']}").status_code == 404


def test_download_returns_the_original_file_as_an_attachment(client: TestClient) -> None:
    document = upload(client, "équipe notes.md", HANDBOOK)["document"]
    response = client.get(f"/api/documents/{document['id']}/file")
    assert response.content == HANDBOOK
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''%C3%A9quipe%20notes.md"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_conversations_can_be_renamed_listed_and_deleted(client: TestClient) -> None:
    conversation = client.post("/api/conversations", json={"title": "Policies"}).json()
    renamed = client.patch(f"/api/conversations/{conversation['id']}", json={"title": "HR questions"}).json()
    assert renamed["title"] == "HR questions"
    assert [c["title"] for c in client.get("/api/conversations").json()] == ["HR questions"]
    assert client.delete(f"/api/conversations/{conversation['id']}").status_code == 204
    assert client.get(f"/api/conversations/{conversation['id']}").status_code == 404
    assert (
        client.post(f"/api/conversations/{conversation['id']}/messages", json={"content": "hi"}).status_code
        == 404
    )


def test_chat_is_rate_limited_per_client(client: TestClient, settings: object) -> None:
    conversation = client.post("/api/conversations", json={}).json()
    limiter = client.app.state.services.chat_limiter  # type: ignore[attr-defined]
    limiter.limit = 1
    ask(client, conversation["id"], "first")
    response = client.post(f"/api/conversations/{conversation['id']}/messages", json={"content": "second"})
    assert response.status_code == 429


def test_validation_errors_and_config(client: TestClient) -> None:
    assert client.post("/api/search", json={"query": ""}).status_code == 422
    assert client.get("/api/documents/not-a-uuid").status_code == 422
    config = client.get("/api/config").json()
    assert config["model"] == "claude-opus-5-5"
    assert ".pdf" in config["acceptedExtensions"]
    assert client.get("/api/health").json() == {"ok": True}
