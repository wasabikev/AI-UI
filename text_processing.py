import re

def format_text(text):
    # Match numbered list items
    list_pattern = re.compile(r"(\d+\.\s[^.]+\.)")
    # Replace with HTML tags
    text = list_pattern.sub(r"<ol>\1</ol>", text)

    # Match Python code blocks
    code_pattern = re.compile(r"(```python\n(.*?)```)", re.DOTALL)
    # Replace with HTML tags
    text = code_pattern.sub(r'<pre><code class="language-python">\2</code></pre>', text)

    # Match JavaScript code blocks
    js_code_pattern = re.compile(r"(```javascript\n(.*?)```)", re.DOTALL)
    # Replace with HTML tags
    text = js_code_pattern.sub(r'<pre><code class="language-javascript">\2</code></pre>', text)


    return text
