/*
 * PixelCraft Studio contact form.
 *
 * IMPORTANT:
 * Replace API_BASE_URL with your API Gateway invoke URL.
 * Include the stage name if your API has one (for example /prod).
 * Do NOT add /contact here; this file adds that route.
 */
const API_BASE_URL = "https://mab9psbvii.execute-api.us-east-1.amazonaws.com/prod".replace(/\/+$/, "");
const CONTACT_ENDPOINT = `${API_BASE_URL}/contact`;

const form = document.getElementById("contact-form");
const submitButton = document.getElementById("submit-btn");
const buttonText = submitButton.querySelector(".btn-text");
const buttonLoader = submitButton.querySelector(".btn-loader");
const successMessage = document.getElementById("success-msg");
const successDetail = document.getElementById("success-detail");
const errorMessage = document.getElementById("error-msg");
const errorDetail = document.getElementById("error-detail");

document.getElementById("year").textContent = new Date().getFullYear();

function showError(message) {
  errorDetail.textContent = message;
  errorMessage.classList.remove("hidden");
  successMessage.classList.add("hidden");
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  buttonText.classList.toggle("hidden", isLoading);
  buttonLoader.classList.toggle("hidden", !isLoading);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  successMessage.classList.add("hidden");
  errorMessage.classList.add("hidden");

  if (!API_BASE_URL || API_BASE_URL.includes("PASTE_YOUR")) {
    showError("The API Gateway URL has not been added to js/app.js yet.");
    return;
  }

  const formData = new FormData(form);
  const payload = {
    name: String(formData.get("name") || "").trim(),
    email: String(formData.get("email") || "").trim(),
    subject: String(formData.get("subject") || "").trim(),
    message: String(formData.get("message") || "").trim()
  };

  if (!payload.name || !payload.email || !payload.message) {
    showError("Please complete your name, email address and message.");
    return;
  }

  setLoading(true);

  try {
    const response = await fetch(CONTACT_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const rawResponse = await response.text();
    let data = {};
    try {
      data = rawResponse ? JSON.parse(rawResponse) : {};
    } catch {
      throw new Error("The server returned an unreadable response. Check your API Gateway and Lambda configuration.");
    }

    if (!response.ok) {
      const details = Array.isArray(data.details) ? data.details.join(" ") : "";
      throw new Error(details || data.error || `Request failed (HTTP ${response.status}).`);
    }

    form.reset();
    successDetail.textContent = data.email_sent === false
      ? "Your message was saved, but the email notification could not be sent. Please contact the site owner another way."
      : "Thank you for contacting PixelCraft Studio. Your message has been received.";
    successMessage.classList.remove("hidden");
  } catch (error) {
    console.error("Contact form submission failed:", error);
    showError(error.message || "Something went wrong. Please try again.");
  } finally {
    setLoading(false);
  }
});
