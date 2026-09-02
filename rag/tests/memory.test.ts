import 'dotenv/config';
import { askSupportAssistant } from '../src/ragChain.js';
import { clearSession } from '../src/memory.js';

async function testMemoryAndFormatting() {
  console.log('=== Testing Vendor-Agnostic Model & Conversational Memory ===\n');

  const sessionId = "test_conversation_123";
  clearSession(sessionId);

  // Turn 1
  console.log('Customer Turn 1: "What is your refund policy?"');
  const res1 = await askSupportAssistant("What is your refund policy?", sessionId);
  console.log(`Assistant:\n${res1.answer}\n`);

  // Turn 2 (Follow-up relying on context from Turn 1)
  console.log('Customer Turn 2 (Follow-up): "How long does the refund take to show up?"');
  const res2 = await askSupportAssistant("How long does the refund take to show up?", sessionId);
  console.log(`Assistant:\n${res2.answer}\n`);

  // Turn 3
  console.log('Customer Turn 3: "And what payment methods can it go back to?"');
  const res3 = await askSupportAssistant("And what payment methods can it go back to?", sessionId);
  console.log(`Assistant:\n${res3.answer}\n`);
}

testMemoryAndFormatting().catch(console.error);
