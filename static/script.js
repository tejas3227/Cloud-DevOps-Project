
const form = document.getElementById("registrationForm");

if (form) {
    const message = document.getElementById("formMessage");
    const submitButton = document.getElementById("submitButton");

    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        // Clear previous messages
        message.textContent = "";
        message.className = "form-message";

        // Disable button while submitting
        submitButton.disabled = true;
        submitButton.textContent = "Registering...";

        try {
            // Send form data to the Flask backend
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form)
            });

            const result = await response.text();

            if (response.ok) {
                // Registration successful
                message.textContent = result;
                message.classList.add("success");

                // Clear form fields
                form.reset();
            } else {
                // Handle validation or server errors
                message.textContent = result;
                message.classList.add("error");
            }

        } catch (error) {
            // Handle network or connection errors
            message.textContent =
                "Unable to contact the server. Please try again.";

            message.classList.add("error");

        } finally {
            // Enable button again
            submitButton.disabled = false;
            submitButton.textContent = "Register Now";
        }
    });
}
