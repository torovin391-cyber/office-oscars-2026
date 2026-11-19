document.getElementById('unlockForm').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('unlockButton');
  const error = document.getElementById('error');
  error.textContent = '';
  button.disabled = true;
  try {
    const response = await fetch('/api/unlock', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({code:document.getElementById('code').value})});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Не удалось открыть приглашение.');
    location.assign('/');
  } catch (err) {error.textContent = err.message;}
  finally {button.disabled = false;}
});
