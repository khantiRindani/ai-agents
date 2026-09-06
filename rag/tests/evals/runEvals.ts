import "dotenv/config";
import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import { askSupportAssistant } from "../../src/ragChain.js";
import { evaluateRetrieval, RetrievalResult } from "./retrievalEvaluator.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
import {
  evaluateStyleAdherence,
  evaluateKeyFacts,
  evaluateBehavior,
  evaluateWithLLMJudge,
  GenerationEvalResult,
} from "./generationEvaluator.js";

interface TestCase {
  id: string;
  category: string;
  question: string;
  expectedDocIds: string[];
  requiredKeyFacts: string[];
  expectedBehavior: "answer" | "fallback" | "fallback_or_clarify" | "refusal";
  notes?: string;
}

interface SampleTranscript {
  testId: string;
  category: string;
  question: string;
  expectedDocIds: string[];
  retrieval: RetrievalResult;
  latencyMs: number;
  answer: string;
  retrievedDocs: { id: string; title: string; excerpt: string }[];
  generationEval: GenerationEvalResult;
}

async function runEvaluationSuite() {
  console.log("\n=========================================================");
  console.log(" 🚀 STARTING RAG EVALUATION HARNESS (SINGLE-TURN MODE)    ");
  console.log("=========================================================\n");

  const datasetPath = path.join(__dirname, "eval_dataset.json");
  const datasetRaw = await fs.readFile(datasetPath, "utf-8");
  const testCases: TestCase[] = JSON.parse(datasetRaw);

  const transcripts: SampleTranscript[] = [];

  for (let i = 0; i < testCases.length; i++) {
    const tc = testCases[i];
    const isolatedSessionId = `eval_single_turn_${tc.id}_${Date.now()}`;
    console.log(`[${i + 1}/${testCases.length}] Evaluating: "${tc.question}" (Session: ${isolatedSessionId})`);

    const startTime = Date.now();
    let response: any = null;
    for (let attempt = 1; attempt <= 4; attempt++) {
      try {
        response = await askSupportAssistant(tc.question, isolatedSessionId);
        break;
      } catch (err: any) {
        if (err?.status === 429 || err?.message?.includes("429") || err?.message?.includes("quota")) {
          const waitSec = attempt * 25;
          console.warn(`[Pipeline RateLimit] Hit rate limit on attempt ${attempt}. Waiting ${waitSec}s...`);
          await new Promise((res) => setTimeout(res, waitSec * 1000));
        } else {
          throw err;
        }
      }
    }
    const latencyMs = Date.now() - startTime;

    const retrievedDocIds = response.sources.map((s) => s.id);
    const retrievalResult = evaluateRetrieval(retrievedDocIds, tc.expectedDocIds);

    // Heuristics
    const styleAdherence = evaluateStyleAdherence(response.answer);
    const keyFactsEval = evaluateKeyFacts(response.answer, tc.requiredKeyFacts);
    const behaviorEval = evaluateBehavior(response.answer, tc.expectedBehavior);

    // Context string for LLM Judge
    const contextString = response.sources
      .map((s, idx) => `[Doc ${idx + 1}] (${s.title}):\n${s.excerpt}`)
      .join("\n\n");

    // LLM-as-a-Judge with Chain-of-Thought Reasoning
    const judgeResult = await evaluateWithLLMJudge(
      tc.question,
      contextString,
      response.answer
    );

    const generationEval: GenerationEvalResult = {
      faithfulnessScore: judgeResult.faithfulnessScore,
      faithfulnessReasoning: judgeResult.faithfulnessReasoning,
      relevanceScore: judgeResult.relevanceScore,
      relevanceReasoning: judgeResult.relevanceReasoning,
      styleAdherence,
      keyFactsRecall: keyFactsEval,
      behaviorCorrect: behaviorEval.passed,
      behaviorNotes: behaviorEval.notes,
    };

    transcripts.push({
      testId: tc.id,
      category: tc.category,
      question: tc.question,
      expectedDocIds: tc.expectedDocIds,
      retrieval: retrievalResult,
      latencyMs,
      answer: response.answer,
      retrievedDocs: response.sources.map((s) => ({
        id: s.id,
        title: s.title,
        excerpt: s.excerpt,
      })),
      generationEval,
    });
  }

  // Aggregate Metrics
  const total = transcripts.length;
  const retrievalHits = transcripts.filter((t) => t.retrieval.hit).length;
  const hitRate = (retrievalHits / total) * 100;
  const meanReciprocalRank =
    transcripts.reduce((acc, t) => acc + t.retrieval.reciprocalRank, 0) / total;

  const faithfulCount = transcripts.filter(
    (t) => t.generationEval.faithfulnessScore === 1
  ).length;
  const faithfulnessRate = (faithfulCount / total) * 100;

  const relevantCount = transcripts.filter(
    (t) => t.generationEval.relevanceScore === 1
  ).length;
  const relevanceRate = (relevantCount / total) * 100;

  const stylePassCount = transcripts.filter(
    (t) => t.generationEval.styleAdherence
  ).length;
  const styleAdherenceRate = (stylePassCount / total) * 100;

  const behaviorPassCount = transcripts.filter(
    (t) => t.generationEval.behaviorCorrect
  ).length;
  const behaviorRate = (behaviorPassCount / total) * 100;

  const latencies = transcripts.map((t) => t.latencyMs).sort((a, b) => a - b);
  const avgLatency = Math.round(
    latencies.reduce((acc, l) => acc + l, 0) / total
  );
  const p50 = latencies[Math.floor(total * 0.5)];
  const p95 = latencies[Math.floor(total * 0.95)];

  // Print Terminal Summary
  console.log("\n=========================================================");
  console.log(" 📊 EVALUATION SUMMARY SCORECARD                         ");
  console.log("=========================================================");
  console.log(`Total Test Cases:            ${total}`);
  console.log(`Retrieval Hit Rate @ K:      ${hitRate.toFixed(1)}% (${retrievalHits}/${total})`);
  console.log(`Mean Reciprocal Rank (MRR):  ${meanReciprocalRank.toFixed(3)}`);
  console.log(`Faithfulness (Groundedness): ${faithfulnessRate.toFixed(1)}% (${faithfulCount}/${total})`);
  console.log(`Answer Relevance Rate:       ${relevanceRate.toFixed(1)}% (${relevantCount}/${total})`);
  console.log(`Style Adherence Rate:        ${styleAdherenceRate.toFixed(1)}% (${stylePassCount}/${total})`);
  console.log(`Behavior & Scope Adherence:  ${behaviorRate.toFixed(1)}% (${behaviorPassCount}/${total})`);
  console.log(`Latency (p50 / p95 / avg):   ${p50}ms / ${p95}ms / ${avgLatency}ms`);
  console.log("=========================================================\n");

  // Write reports
  const reportsDir = path.join(__dirname, "reports");
  await fs.mkdir(reportsDir, { recursive: true });

  const jsonReportPath = path.join(reportsDir, "latest_eval_run.json");
  await fs.writeFile(
    jsonReportPath,
    JSON.stringify(
      {
        timestamp: new Date().toISOString(),
        summary: {
          total,
          hitRate,
          meanReciprocalRank,
          faithfulnessRate,
          relevanceRate,
          styleAdherenceRate,
          behaviorRate,
          avgLatency,
          p50,
          p95,
        },
        transcripts,
      },
      null,
      2
    )
  );

  const mdReportPath = path.join(reportsDir, "latest_eval_report.md");
  const markdownReport = generateMarkdownReport({
    timestamp: new Date().toISOString(),
    total,
    hitRate,
    meanReciprocalRank,
    faithfulnessRate,
    relevanceRate,
    styleAdherenceRate,
    behaviorRate,
    avgLatency,
    p50,
    p95,
    transcripts,
  });

  await fs.writeFile(mdReportPath, markdownReport);
  console.log(`✅ Detailed JSON Report: ${jsonReportPath}`);
  console.log(`✅ Detailed Markdown Transcript Report: ${mdReportPath}\n`);
}

function generateMarkdownReport(data: any): string {
  return `# RAG Evaluation Run Report
Generated: **${data.timestamp}**

## Executive Scorecard

| Metric | Score | Target | Status |
| :--- | :--- | :--- | :--- |
| **Retrieval Hit Rate @ K** | **${data.hitRate.toFixed(1)}%** | ≥ 90% | ${data.hitRate >= 90 ? "🟢 Pass" : "🔴 Review"} |
| **Mean Reciprocal Rank (MRR)** | **${data.meanReciprocalRank.toFixed(3)}** | ≥ 0.85 | ${data.meanReciprocalRank >= 0.85 ? "🟢 Pass" : "🟡 Watch"} |
| **Faithfulness / Groundedness** | **${data.faithfulnessRate.toFixed(1)}%** | ≥ 95% | ${data.faithfulnessRate >= 95 ? "🟢 Pass" : "🔴 Review"} |
| **Answer Relevance** | **${data.relevanceRate.toFixed(1)}%** | ≥ 95% | ${data.relevanceRate >= 95 ? "🟢 Pass" : "🟡 Watch"} |
| **Style & Anti-Filler Adherence**| **${data.styleAdherenceRate.toFixed(1)}%** | 100% | ${data.styleAdherenceRate === 100 ? "🟢 Pass" : "🟡 Watch"} |
| **Behavior & Scope Guard** | **${data.behaviorRate.toFixed(1)}%** | 100% | ${data.behaviorRate === 100 ? "🟢 Pass" : "🔴 Review"} |
| **Latency (p50 / p95)** | **${data.p50}ms / ${data.p95}ms** | < 2500ms | 🟢 Normal |

---

## Single-Turn Test Case Transcripts & Reasoning

${data.transcripts
      .map(
        (t: SampleTranscript, idx: number) => `
### ${idx + 1}. [${t.category}] ${t.testId}
- **Question**: "${t.question}"
- **Latency**: \`${t.latencyMs}ms\`
- **Retrieval**: ${t.retrieval.hit ? "✅ Hit" : "❌ Miss"} (Reciprocal Rank: \`${t.retrieval.reciprocalRank.toFixed(2)}\`)
- **Retrieved Docs**: ${t.retrievedDocs.map((d) => `\`${d.id}\` (${d.title})`).join(", ") || "None"}
- **Expected Doc IDs**: ${t.expectedDocIds.join(", ") || "None (Out of Domain)"}

#### Generated Answer
> ${t.answer.replace(/\n/g, "\n> ")}

#### Evaluator Reasoning & Verdicts
- **Faithfulness**: ${t.generationEval.faithfulnessScore === 1 ? "✅ Grounded" : "❌ Hallucinated"}
  - *Reasoning*: ${t.generationEval.faithfulnessReasoning}
- **Relevance**: ${t.generationEval.relevanceScore === 1 ? "✅ Relevant" : "❌ Irrelevant"}
  - *Reasoning*: ${t.generationEval.relevanceReasoning}
- **Style Adherence**: ${t.generationEval.styleAdherence ? "✅ Clean (No greeting filler)" : "⚠️ Contained prohibited greeting"}
- **Behavior Note**: ${t.generationEval.behaviorNotes}
`
      )
      .join("\n---\n")}
`;
}

runEvaluationSuite().catch(console.error);
