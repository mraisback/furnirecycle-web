const input = document.getElementById('pdfs');
const list = document.getElementById('fileList');
const order = document.getElementById('order');

let currentFiles = [];

function renderList() {
  list.innerHTML = '';
  currentFiles.forEach((file, index) => {
    const li = document.createElement('li');
    li.className = 'file-item';
    li.textContent = `${index + 1}. ${file.name}`;
    li.draggable = true;
    li.dataset.name = file.name;
    list.appendChild(li);
  });
  order.value = currentFiles.map((f) => f.name).join(',');
}

input.addEventListener('change', () => {
  currentFiles = Array.from(input.files);
  renderList();
});

list.addEventListener('dragstart', (event) => {
  const target = event.target;
  if (!target.classList.contains('file-item')) return;
  target.classList.add('dragging');
  event.dataTransfer.setData('text/plain', target.dataset.name);
});

list.addEventListener('dragend', (event) => {
  event.target.classList.remove('dragging');
});

list.addEventListener('dragover', (event) => {
  event.preventDefault();
  const draggingName = event.dataTransfer.getData('text/plain');
  const target = event.target.closest('.file-item');
  if (!target || target.dataset.name === draggingName) return;

  const draggingIndex = currentFiles.findIndex((f) => f.name === draggingName);
  const targetIndex = currentFiles.findIndex((f) => f.name === target.dataset.name);
  if (draggingIndex < 0 || targetIndex < 0) return;

  const [draggingFile] = currentFiles.splice(draggingIndex, 1);
  currentFiles.splice(targetIndex, 0, draggingFile);
  renderList();
});
