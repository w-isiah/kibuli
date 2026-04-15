function showFlashMessage(message, type = 'success') {
  // Create a new flash message element
  const messageElement = document.createElement('div');
  messageElement.classList.add('flash-message');
  
  // Set the message text
  messageElement.innerText = message;

  // Optional: You can change the background color based on the type of message
  if (type === 'error') {
    messageElement.style.backgroundColor = '#f44336'; // Red background for error
  } else if (type === 'warning') {
    messageElement.style.backgroundColor = '#ff9800'; // Orange background for warning
  }

  // Append the message to the container
  const container = document.getElementById('flash-message-container');
  container.appendChild(messageElement);

  // Display the flash message container
  container.style.display = 'block';

  // Set a timeout to fade out the message after 3 seconds
  setTimeout(() => {
    messageElement.style.opacity = '0';
  }, 2000);

  // Remove the message after it's fully faded out
  setTimeout(() => {
    messageElement.remove();
    
    // If there are no more messages, hide the container
    if (container.children.length === 0) {
      container.style.display = 'none';
    }
  }, 3000);
}

