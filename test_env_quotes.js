// Test how Node.js/Vite handles quotes in env vars
const testValue1 = '"quoted value"';
const testValue2 = 'unquoted value';

console.log('Raw value with quotes:', testValue1);
console.log('Raw value without quotes:', testValue2);

// Simulate what happens when these are read from env
console.log('\nAfter JSON.stringify (as Vite does):');
console.log('Quoted:', JSON.stringify(testValue1));
console.log('Unquoted:', JSON.stringify(testValue2));
EOF && node test_env_quotes.js && rm test_env_quotes.js < /dev/null