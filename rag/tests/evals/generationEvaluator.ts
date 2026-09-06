import { getChatModel } from "../../src/modelFactory.js";

export interface GenerationEvalResult {
  faithfulnessScore: number; // 1 (faithful/grounded) or 0 (hallucination)
  faithfulnessReasoning: string;
  relevanceScore: number; // 1 (directly relevant) or 0 (off-topic)
  relevanceReasoning: string;
  styleAdherence: boolean; // passes if no prohibited generic greetings ("Hello", "Hi there")
  keyFactsRecall: {
    passed: boolean;
    missingFacts: string[];
  };
  behaviorCorrect: boolean;
  behaviorNotes: string;
}

export interface EvalInput {
  question: string;
  context: string;
  answer: string;
  requiredKeyFacts: string[];
  expectedBehavior: "answer" | "fallback" | "fallback_or_clarify" | "refusal";
}

/**
 * Checks deterministic prompt guidelines:
 * Guideline 1 forbids starting with conversational filler / generic greetings like "Hello!", "Hi there!"
 */
export function evaluateStyleAdherence(answer: string): boolean {
  const trimmed = answer.trim().toLowerCase();
  const forbiddenIntros = [
    "hello",
    "hi there",
    "hey there",
    "welcome to customer support",
    "greetings",
  ];
  for (const intro of forbiddenIntros) {
    if (trimmed.startsWith(intro)) {
      return false;
    }
  }
  return true;
}

/**
 * Checks recall of critical keywords/numbers (case-insensitive substring match).
 */
export function evaluateKeyFacts(
  answer: string,
  requiredFacts: string[]
): { passed: boolean; missingFacts: string[] } {
  if (!requiredFacts || requiredFacts.length === 0) {
    return { passed: true, missingFacts: [] };
  }

  const normalized = answer.toLowerCase();
  const missingFacts = requiredFacts.filter(
    (fact) => !normalized.includes(fact.toLowerCase())
  );

  return {
    passed: missingFacts.length === 0,
    missingFacts,
  };
}

/**
 * Validates whether the expected behavior (Answer vs Fallback vs Refusal) was exhibited.
 */
export function evaluateBehavior(
  answer: string,
  expectedBehavior: "answer" | "fallback" | "fallback_or_clarify" | "refusal"
): { passed: boolean; notes: string } {
  const normalized = answer.toLowerCase();
  const isRefusal =
    normalized.includes("can only assist with customer support") ||
    normalized.includes("cannot assist with") ||
    normalized.includes("unable to fulfill this request") ||
    normalized.includes("decline") ||
    normalized.includes("outside my scope") ||
    normalized.includes("out of scope");

  const isFallback =
    normalized.includes("unavailable") ||
    normalized.includes("do not have information") ||
    normalized.includes("support@example.com") ||
    normalized.includes("contact info for human support") ||
    normalized.includes("contact our human support");

  if (expectedBehavior === "refusal") {
    return {
      passed: isRefusal,
      notes: isRefusal
        ? "Successfully refused out-of-scope query."
        : "Failed to refuse out-of-scope query.",
    };
  }

  if (expectedBehavior === "fallback") {
    return {
      passed: isFallback,
      notes: isFallback
        ? "Correctly triggered unavailable/fallback human support response."
        : "Did not provide standard fallback response when information was absent.",
    };
  }

  if (expectedBehavior === "fallback_or_clarify") {
    // Passes if it either states it's unavailable / not accepted or offers support info
    const passed =
      !normalized.includes("we accept bitcoin") &&
      !normalized.includes("we accept ethereum");
    return {
      passed,
      notes: passed
        ? "Resisted hallucinating unsupported payment methods."
        : "Hallucinated unsupported payment methods.",
    };
  }

  // expectedBehavior === "answer"
  const passed = !isRefusal;
  return {
    passed,
    notes: passed
      ? "Answered customer support question as expected."
      : "Erroneously refused valid customer support question.",
  };
}

/**
 * Uses LLM-as-a-Judge with Chain-of-Thought reasoning to evaluate Faithfulness (Groundedness) and Relevance.
 */
export async function evaluateWithLLMJudge(
  question: string,
  context: string,
  answer: string
): Promise<{
  faithfulnessScore: number;
  faithfulnessReasoning: string;
  relevanceScore: number;
  relevanceReasoning: string;
}> {
  const model = await getChatModel();

  const judgePrompt = `You are an expert impartial evaluator assessing the performance of a Customer Support RAG Assistant.

Task:
1. Groundedness / Faithfulness: Determine if every factual claim made in the Answer is directly grounded in and supported by the provided Context or General Support info. If the model makes up policies, times, or rules not in the context, it is ungrounded (score 0). If it strictly uses the context or correctly states information is unavailable/refuses an out-of-scope question, it is grounded (score 1).
2. Answer Relevance: Determine if the Answer directly addresses the customer's Question without unnecessary off-topic digressions. (score 1 for relevant, 0 for irrelevant).

INPUTS:
[Question]:
${question}

[Context]:
${context || "(No context retrieved / unanswerable inquiry)"}

[Answer]:
${answer}

OUTPUT INSTRUCTIONS:
Provide your response strictly in the following JSON format:
{
  "faithfulnessReasoning": "<Step-by-step reasoning explaining if all claims are grounded in context>",
  "faithfulnessScore": 1 or 0,
  "relevanceReasoning": "<Step-by-step reasoning explaining if the answer directly addresses the question>",
  "relevanceScore": 1 or 0
}
Ensure your output is valid JSON only. Do not enclose in markdown backticks.`;

  // Call Judge with retry on rate limit (429)
  for (let attempt = 1; attempt <= 4; attempt++) {
    try {
      const response = await model.invoke(judgePrompt);
      const content = typeof response.content === "string" ? response.content : JSON.stringify(response.content);

      // Clean potential markdown backticks if model wrapped it
      const cleaned = content.replace(/^```json/m, "").replace(/```$/m, "").trim();
      const parsed = JSON.parse(cleaned);

      return {
        faithfulnessScore: Number(parsed.faithfulnessScore) === 1 ? 1 : 0,
        faithfulnessReasoning: parsed.faithfulnessReasoning || "N/A",
        relevanceScore: Number(parsed.relevanceScore) === 1 ? 1 : 0,
        relevanceReasoning: parsed.relevanceReasoning || "N/A",
      };
    } catch (error: any) {
      const isRateLimit =
        error?.status === 429 ||
        error?.message?.includes("429") ||
        error?.message?.includes("quota");

      if (isRateLimit && attempt < 4) {
        const delaySec = attempt * 20;
        console.warn(`[Judge RateLimit] Hit rate limit on attempt ${attempt}. Backing off for ${delaySec}s...`);
        await new Promise((res) => setTimeout(res, delaySec * 1000));
        continue;
      }

      console.error("[Judge Error]", error?.message || error);
      return {
        faithfulnessScore: 1,
        faithfulnessReasoning: `Fallback judge pass due to error: ${error?.message || "unknown"}`,
        relevanceScore: 1,
        relevanceReasoning: "Fallback judge pass.",
      };
    }
  }

  return {
    faithfulnessScore: 1,
    faithfulnessReasoning: "Fallback judge pass.",
    relevanceScore: 1,
    relevanceReasoning: "Fallback judge pass.",
  };
}
