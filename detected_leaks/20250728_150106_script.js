# --- DETECTION METADATA ---
# File Path: script.js
# File Size: 0.00 KB
# Raw URL: https://github.com/valientjuno/project_list/raw/03d6299f65a4e3b5ea3a7d754c6a19d8b94a8e63/script.js
#
# Detections:
# - Line 15: REAL_KEY (hex key) -> "  // you will need to get the output using the same method you did for the ..."
# --- END METADATA ---

//
//
// NOTE: PLEASE READ EACH INSTRUCTION COMMENT CAREFULLY TO HELP YOU PROCESS THIS PROJECT
// IF YOU ARE STUCK ASK AN INSTRUCTOR FOR HELP, ALWAYS WRITE THE CODE BELOW THE ASSIGNMENTS.

productArray = [];
function addProduct() {
  // Assignment 1
  // You need to change the id that this collects to product.
  let input = document.getElementById("output").value;
  // You will need to create a div using javascript,
  // Use this site to help you understand how: https://www.w3schools.com/jsref/met_document_createelement.asp

  // Once you create create a div,
  // you will need to get the output using the same method you did for the input
  // Except you do not need to include the value at the end.

  // CHALLENGE SECTION:
  // If you feel up for a challenge, try and use an if statement if(condition){run this code}
  // to return an alert if the input is empty. You will need to get the id as in previous assignments above
  // and then get the value at the end and check if they are strictly equal to an empty string.
  // If the code you will want to run after checking the condition is to run the alert method.
  // If you do not know the alert method, look it up on google using the w3schools,
  // do not forget to include a return false at the end to not reload your webpage.

  // Assignment 2:
  // You need to put the value of the input into an array to call later.
  // That means you will need to assign your input using brackets around it
  // to a newProduct variable, remember that assign can mean the equals sign(=).
  let newProduct = { input };
  // Hint: You could push your product to a new array once you create a new variable
  // that makes a single object {} with the product variable you made above.
  // Please look up how to use push on an array here: https://www.w3schools.com/jsref/jsref_push.asp
  // use console.log and pass in the product array to check if you have it setup correctly.
  // console.log(productArray)

  // Assignment 3:
  // Hint: Use a loop(look up the javascript loop on w3schools.) on your product array and set the max length of the loop to the array using
  // dot notation (array.length) and then you do the following:
  //
  // set the input to empty, similar how you would check in the if statement previously,
  // just get document.getelementbyid then set the .value to an empty string.

  // then set the output div to display block, its normally set to none, which means invisible
  // This means that you need to get your output variable use dot notation to set style.display = "block"

  // set the div.textContent equal to the the array index number [i] and dot notation of the product
  // `${productArray[i].your input}`

  // finally use the appendChild method from the output variable you had from earlier.
  // output.appendChild(yourdivnamehere)
  console.log(addProduct);
  // this line is to prevent the webpage from reloading. DO NOT MODIFY IT.
  return false;
}
