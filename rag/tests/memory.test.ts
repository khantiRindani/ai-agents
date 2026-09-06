import 'dotenv/config';
import assert from 'node:assert/strict';
import { askSupportAssistant } from '../src/ragChain.js';
import {
  getSession,
  clearSession,
  getSessionHistory,
  getAllSessions,
  addMessageToSession,
} from '../src/memory.js';

async function testMemoryAndSessionManagement() {
  console.log('\n=============================================================');
  console.log(' 🧠 TESTING SESSION MANAGEMENT & CONVERSATIONAL MEMORY       ');
  console.log('=============================================================\n');

  const sessionIdA = `test_session_A_${Date.now()}`;
  const sessionIdB = `test_session_B_${Date.now()}`;

  // Ensure clean state
  clearSession(sessionIdA);
  clearSession(sessionIdB);

  console.log('👉 [1/4] Testing Session Creation & Isolation...');
  const sessionA = getSession(sessionIdA);
  assert.equal(sessionA.messages.length, 0, 'New session should have 0 messages');
  assert.equal(sessionA.id, sessionIdA);

  const sessionB = getSession(sessionIdB);
  assert.notEqual(sessionA.id, sessionB.id, 'Session IDs must be distinct');
  console.log('   ✅ Initial session states isolated and clean.');

  console.log('\n👉 [2/4] Executing Turn 1 and Verifying In-Memory Persistence...');
  const q1 = "What is your refund policy?";
  const res1 = await askSupportAssistant(q1, sessionIdA);
  
  // Verify Turn 1 is stored in memory
  const historyAfterTurn1 = getSessionHistory(sessionIdA);
  assert.equal(historyAfterTurn1.length, 2, 'Session should store exactly 1 human turn and 1 ai response (2 messages)');
  assert.equal(historyAfterTurn1[0].sender, 'user');
  assert.equal(historyAfterTurn1[0].text, q1, 'Turn 1 prompt should be preserved in memory');
  assert.equal(historyAfterTurn1[1].sender, 'bot');
  assert.equal(historyAfterTurn1[1].text, res1.answer, 'Turn 1 assistant answer should be stored');

  // Verify Session B was not polluted
  const historySessionB = getSessionHistory(sessionIdB);
  assert.equal(historySessionB.length, 0, 'Session B should remain unaffected by Session A interactions');
  console.log('   ✅ Turn 1 recorded in memory with verified role, prompt text, and session isolation.');

  console.log('\n👉 [3/4] Executing Follow-Up Turn & Verifying Context Retention...');
  const q2 = "How long does it take to process back to my card?";
  const res2 = await askSupportAssistant(q2, sessionIdA);

  const historyAfterTurn2 = getSessionHistory(sessionIdA);
  assert.equal(historyAfterTurn2.length, 4, 'Session should now contain 4 messages (2 human, 2 ai)');
  assert.equal(historyAfterTurn2[2].text, q2, 'Turn 2 prompt must be appended');
  
  // Follow-up answer should retain context (e.g. business days)
  const normAns2 = res2.answer.toLowerCase();
  assert(
    normAns2.includes("5-7") || normAns2.includes("business days") || normAns2.includes("refund"),
    'Turn 2 response should correctly resolve follow-up context about refund duration'
  );
  console.log('   ✅ Follow-up resolved correctly with cumulative message history.');

  console.log('\n👉 [4/4] Testing Context Window Sliding Buffer (Max 10 Messages)...');
  // Add simulated messages to exceed the 10-message sliding window limit
  for (let i = 1; i <= 8; i++) {
    addMessageToSession(sessionIdA, i % 2 === 0 ? "human" : "ai", `Simulated message ${i}`);
  }
  const sessionAfterOverflow = getSession(sessionIdA);
  assert.equal(
    sessionAfterOverflow.messages.length,
    10,
    `Memory buffer should cap at exactly 10 messages (received ${sessionAfterOverflow.messages.length})`
  );

  // Test session deletion / clearing
  const cleared = clearSession(sessionIdA);
  assert.equal(cleared, true, 'Session A should be successfully deleted');
  assert.equal(getSessionHistory(sessionIdA).length, 0, 'Cleared session history should be empty');
  console.log('   ✅ Sliding window (10 messages) enforced and session cleared successfully.');

  console.log('\n🎉 ALL MEMORY & SESSION MANAGEMENT TESTS PASSED!\n');
}

testMemoryAndSessionManagement().catch((err) => {
  console.error('\n❌ Memory test failed:', err);
  process.exit(1);
});
