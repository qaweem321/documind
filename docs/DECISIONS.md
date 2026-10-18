# Design decisions

Why DocuMind is built the way it is, and what each choice costs. Each section answers a question an
interviewer or contributor is likely to ask.

## 1. How does a question become an answer?

1. **Retrieve.** The question (plus the previous question, for follow-ups) is embedded and run through
   hybrid search. The 8 best passages come back.
2. **Generate.** Claude gets the conversation so far as plain text, then the new question with each
   passage attached as its own document block with citations enabled.
3. **Cite.** Claude's answer streams back as text blocks. Blocks that rely on a passage carry a
   citation naming the passage (`document_index`) and the exact sentence quoted (`cited_text`).
4. **Stream.** The backend forwards this to the browser as server-sent events: `sources`, then `text`
   and `citation` events as Claude writes, then `done`. The finished answer is stored with its
   segments, citations and passages, so a reloaded chat looks the same.

## 2. Why Claude's citations instead of asking for "[1]" markers?

A prompt that says "cite sources as [1]" produces numbers that are usually right, sometimes wrong, and
never checkable. With the API's citations feature each citation points at a passage and quotes the
exact text from it, so the interface can highlight the quoted sentence. The answer can't cite a
passage that wasn't in the prompt.

**Trade-off:** citations add some input tokens, and they can't be combined with structured outputs.
Neither matters for chat.

## 3. Why hybrid search, and what does it buy?

Embeddings match meaning ("my laptop when I quit" finds "returned within 10 business days after your
last day") but blur exact terms: error codes, product names, IDs. Postgres full-text search is the
opposite. DocuMind runs both in one SQL statement and merges them with Reciprocal Rank Fusion: each
list adds `1 / (60 + rank)` for a passage, so a passage near the top of both wins, and the two scores
never need to be on the same scale.

Measured with `backend/evals/retrieval.py` (20 questions over the sample handbook, phrased without
the policy's wording, 500-character passages):

| Method        | Hit@1 | Recall@5 |
| ------------- | ----: | -------: |
| Keyword only  |   85% |      95% |
| Semantic only |   90% |     100% |
| Hybrid        |   90% |     100% |

On this small set hybrid fixes keyword search's recall gap and matches semantic search. Its advantage
shows on exact terms, which this sample has few of. The evaluation exists so changes to chunking,
weights or models are measured instead of guessed.

**Ties go to the better semantic match.** Postgres full-text ranking doesn't know how rare a word is:
for _"How long is a sabbatical?"_ a passage that merely contains "long" ranked first by keyword while
the sabbatical passage ranked first by meaning, and the two fused scores were exactly equal. Breaking
ties by semantic rank fixed that without a tuned weight (weights of 0.3 to 1.0 for keyword results
made no measurable difference on this set).

## 4. Why local embeddings?

`BAAI/bge-small-en-v1.5` through fastembed (ONNX) runs on the CPU in a few milliseconds per passage, needs
no API key, and costs nothing per call. The Docker image includes the model, so containers start offline.
Only answer generation needs an API key.

**Trade-off:** a hosted embedding model would retrieve somewhat better on hard questions. Switching is a
one-class change (`Embedder` protocol), plus a migration if the vector size differs from 384.

## 5. Why pgvector instead of a vector database?

Passages, documents, conversations and messages live in one Postgres database: one backup, foreign
keys (deleting a document deletes its passages), transactions, and filters written in SQL. HNSW
indexes keep vector search fast into the millions of rows. It runs anywhere Postgres does, including
Supabase and Neon.

## 6. How are documents processed?

Uploads are stored first (the original bytes, in their own table so listing documents never reads
them), and the request returns at once. A background queue then extracts text page by page (pypdf),
splits each page into ~500-character passages on paragraph, line and sentence boundaries (LangChain's
recursive splitter), embeds them in batches of 64, and writes them with one `COPY` in one
transaction. Splitting per page keeps a page number on every passage, so citations say "p. 4".

Documents still processing when the app stops are queued again at startup. The same file uploaded
twice (same SHA-256) returns the existing document.

**Trade-off:** one queue per process. Many uploads at once wait their turn; several app instances would
each run their own queue, which is safe because processing a document again replaces its passages.

## 7. Why 500-character passages?

Smaller passages make citations precise (the highlighted quote is the actual answer, not a page of
context) and improved hit@1 in the evaluation. Neighbouring passages overlap by 100 characters, so a
sentence split at a boundary still appears whole in one of them.

## 8. How do follow-up questions work?

"And for contractors?" means nothing on its own. Retrieval searches the previous question and the new
one together, and Claude receives the last six exchanges as plain text. Passages from earlier turns are
not resent; the new question retrieves its own.

**Trade-off:** a model-written standalone query would handle long, winding conversations better, at the
cost of an extra API call before every answer.

## 9. What happens if Claude declines, errors, or the browser disconnects?

Requests enable server-side fallbacks (`fallbacks: "default"`), so if a safety classifier declines, the API
retries on Anthropic's recommended fallback model within the same stream. A remaining refusal, an
invalid key, rate limiting or a network failure becomes a readable message in the chat. If the
browser disconnects or the user presses Stop, the partial answer is still saved (the save is shielded
from cancellation).

## 10. What isn't there (yet)?

- **Accounts.** DocuMind is a single-team tool: run it on a private network or behind your SSO proxy.
  The chat endpoint is rate-limited per IP so a leaked URL can't run up an API bill quickly.
- **OCR.** Scanned PDFs have no text layer; the upload says so instead of storing an empty document.
- **More formats.** PDF, Markdown and plain text cover most handbooks and docs; Word files would be a
  new extractor in `extract.py`.
