import 'dotenv/config';
import assert from 'node:assert/strict';
import { askSupportAssistant } from '../src/ragChain.js';

async function testRAGSmoke() {
  console.log('\n=============================================================');
  console.log(' 🔌 RAG PIPELINE INTEGRATION & SMOKE TEST                    ');
  console.log('=============================================================\n');

  const testQuery = "What is your return policy?";
  const testSessionId = `smoke_test_${Date.now()}`;

  console.log(`Executing smoke query: "${testQuery}" (Session: ${testSessionId})...`);
  const startTime = Date.now();
  const res = await askSupportAssistant(testQuery, testSessionId);
  const durationMs = Date.now() - startTime;

  // 1. Validate response contract structure
  assert(res && typeof res === 'object', 'Response must be an object');
  assert(typeof res.answer === 'string' && res.answer.trim().length > 0, 'Response answer must be a non-empty string');
  assert(Array.isArray(res.sources), 'Response sources must be an array');
  assert.equal(res.sessionId, testSessionId, 'Response sessionId must match input sessionId');

  // 2. Validate source document contract
  assert(res.sources.length > 0, 'Expected at least 1 retrieved source document');
  const firstSource = res.sources[0];
  assert(typeof firstSource.id === 'string', 'Source document must include string id');
  assert(typeof firstSource.title === 'string', 'Source document must include string title');
  assert(typeof firstSource.category === 'string', 'Source document must include string category');
  assert(typeof firstSource.excerpt === 'string', 'Source document must include string excerpt');

  console.log(`\n✅ Contract verified:`);
  console.log(`   - Answer length: ${res.answer.length} chars`);
  console.log(`   - Retrieved sources: ${res.sources.length} (${res.sources.map(s => s.title).join(', ')})`);
  console.log(`   - Roundtrip duration: ${durationMs}ms`);

  console.log('\n🎉 RAG PIPELINE SMOKE TEST PASSED!\n');
}

testRAGSmoke().catch((err) => {
  console.error('\n❌ RAG Smoke Test Failed:', err);
  process.exit(1);
});
