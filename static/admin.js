document.getElementById('exportForm').addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('exportButton');
  const error = document.getElementById('error');
  const token = document.getElementById('token').value.trim();
  error.textContent = '';
  button.disabled = true;
  try {
    const response = await fetch('/api/admin/export.csv', {headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'});
    if (!response.ok) {
      const info = await response.json().catch(() => ({}));
      throw new Error(info.error || 'Не удалось скачать CSV.');
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = 'office-oscars-rsvp.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  } catch (err) { error.textContent = err.message; }
  finally {button.disabled = false;}
});
