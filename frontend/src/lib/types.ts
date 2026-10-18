// Mirrors backend/app/schemas.py.

export type DocumentStatus = "processing" | "ready" | "failed";

export type Doc = {
  id: string;
  title: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  pageCount: number | null;
  chunkCount: number;
  status: DocumentStatus;
  error: string | null;
  createdAt: string;
};

export type UploadResult = {
  document: Doc | null;
  filename: string;
  duplicate: boolean;
  error: string | null;
};

export type Source = {
  index: number;
  chunkId: number;
  documentId: string;
  documentTitle: string;
  page: number | null;
  content: string;
  score: number;
};

export type Citation = { sourceIndex: number; citedText: string };
export type Segment = { text: string; citations: Citation[] };

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  segments: Segment[] | null;
  sources: Source[] | null;
  createdAt: string;
};

export type Conversation = {
  id: string;
  title: string;
  documentIds: string[] | null;
  createdAt: string;
  updatedAt: string;
};

export type ConversationDetail = Conversation & { messages: Message[] };

export type AppConfig = {
  model: string;
  maxUploadMb: number;
  acceptedExtensions: string[];
};
