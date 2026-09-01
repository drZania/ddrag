export interface ApplicationInformation {
  question: string;
  answer: string;
}

const applicationInformationByQuestion: Record<string, string> = {
  "what is ddrag": "DDRAG stands for Drag, Drop, Retrieve, Augment, Generate. It is a document-based Retrieval-Augmented Generation application that answers questions using content retrieved from your uploaded documents.",
  "what is this app": "DDRAG is a document-based Retrieval-Augmented Generation application. Upload documents, then ask questions to receive answers grounded in retrieved document content with source metadata.",
  "who created this": "DDRAG was created by Dino Rey Barliso as a portfolio project.",
  "what can i do here": "You can upload PDF, TXT, Markdown, and DOCX documents. DDRAG processes them, retrieves relevant content for your questions, generates grounded answers, and displays the source metadata used for each new answer.",
  "how does this application work": "DDRAG processes your uploaded documents into searchable content. When you ask a question, it retrieves relevant document content, generates an answer from that context, and displays the actual source metadata returned by the retrieval workflow.",
  "what types of documents can i upload": "DDRAG accepts PDF, TXT, Markdown, and DOCX documents up to 10 MB.",
};

export const applicationInformationPrompts = [
  "What is DDRAG?",
  "What can I do here?",
  "How does this application work?",
] as const;

function normalizeQuestion(question: string): string {
  return question.trim().toLowerCase().replace(/[?!.]+$/, "").replace(/\s+/g, " ");
}

export function getApplicationInformation(question: string): ApplicationInformation | null {
  const normalizedQuestion = normalizeQuestion(question);
  const answer = applicationInformationByQuestion[normalizedQuestion];
  return answer ? { question: question.trim(), answer } : null;
}
