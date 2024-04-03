import requests
import streamlit.components.v1 as components

# Define the base URL of your Flask app
base_url = 'http://144.126.241.79/learning_resource'

# Define the route endpoint and parameters
route = '/generate_learning_resource_html_format'
params = {
    'param1': 'python',
    'param2': None,
    'param3': 'microsoft'
}

# Make a GET request to the Flask route with the parameters
response = requests.get(f"{base_url}{route}", params=params)

# Print the response text (or process it in another way)
components.html(response.text, scrolling=True, width=1280, height=720)