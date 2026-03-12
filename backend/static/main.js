// moved to backup_words_detector
// ---------- Text detection ----------
async function runDetection() {
  const text = document.getElementById("textInput").value;
  const resEl = document.getElementById("textResult");
  const res = await fetch("/api/detect", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text})
  });
  const data = await res.json();
  resEl.textContent = JSON.stringify(data, null, 2);
}
// ---------- File upload ----------
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("uploadForm");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById("fileInput");
      const resEl = document.getElementById("fileResult");
      const formData = new FormData();
      formData.append("file", fileInput.files[0]);
      const res = await fetch("/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      resEl.textContent = JSON.stringify(data, null, 2);
    });
  }
  if (document.getElementById("chatWindow")) {
    initChat();
  }
});
// moved to backup_words_detector
