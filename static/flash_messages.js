function displayFlashMessage(category, message) {
    const container = document.getElementById("flash-messages-container");
    const flashMessage = document.createElement("div");
    flashMessage.className = `alert alert-${category}`;
    flashMessage.innerText = message;
    container.appendChild(flashMessage);

    setTimeout(() => {
        flashMessage.remove();
    }, 3000);
}

function processFlashMessages() {
    const flashMessages = JSON.parse(document.getElementById("flashed-messages-data").textContent);
    for (const [category, message] of flashMessages) {
        displayFlashMessage(category, message);
    }
}
