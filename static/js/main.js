const form = document.getElementById("genForm");
const result = document.getElementById("result");
const links = document.getElementById("links");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  links.innerHTML = "";
  result.classList.add("d-none");

  const fd = new FormData();
  fd.append("script", document.getElementById("script").value || "");
  fd.append("language", document.getElementById("language").value);
  fd.append("voice", document.getElementById("voice").value || "");
  fd.append("style", document.getElementById("style").value);
  fd.append("aspect", document.getElementById("aspect").value);
  fd.append("target_seconds", document.getElementById("target_seconds").value || "60");

  try {
    const res = await axios.post("/generate", fd);
    if (res.data.ok) {
      result.classList.remove("d-none");
      addLink("🎬 MP4 Video", res.data.video_url);
      if (res.data.srt_url) addLink("💬 Subtitles (.srt)", res.data.srt_url);
      if (res.data.audio_url) addLink("🎙️ Voice-Over (.wav)", res.data.audio_url);
    } else {
      alert(res.data.error || "Failed to generate video.");
    }
  } catch (err) {
    alert(err?.response?.data?.error || err.message || "Something went wrong.");
  }
});

function addLink(label, href) {
  const li = document.createElement("li");
  li.className = "list-group-item d-flex justify-content-between align-items-center";
  const a = document.createElement("a");
  a.href = href;
  a.textContent = label;
  a.className = "btn btn-success";
  li.appendChild(document.createTextNode(href.split('/').pop()));
  li.appendChild(a);
  links.appendChild(li);
}
