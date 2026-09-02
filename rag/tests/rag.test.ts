import 'dotenv/config';
import { askSupportAssistant } from '../src/ragChain.js';

async function testRAG() {
  console.log('=== Testing Support RAG System ===\n');

  const queries = [
    "How can I track my order delivery?",
    "Can I return an item after 20 days?",
    "What payment methods do you support?"
  ];

  for (const q of queries) {
    console.log(`\n Question: "${q}"`);
    const res = await askSupportAssistant(q);
    console.log(` Answer:\n${res.answer}`);
    console.log(` Sources (${res.sources.length}):`);
    res.sources.forEach((s, idx) => {
      console.log(`   [${idx + 1}] ${s.title} (${s.category})`);
    });
    console.log('--------------------------------------------------');
  }
}

testRAG().catch(console.error);
