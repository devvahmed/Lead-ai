import os, urllib.request, json
key = os.environ.get('GROQ_API_KEY', '')
headers = {
    'Authorization': 'Bearer ' + key,
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0'
}
for model in ['groq/compound-mini', 'openai/gpt-oss-20b', 'qwen/qwen3.6-27b']:
    payload = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': 'Reply with the single word: OK'}],
        'max_tokens': 10
    }).encode()
    req = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=payload, headers=headers, method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            reply = data['choices'][0]['message']['content']
            print(model + ': SUCCESS -> ' + repr(reply))
    except urllib.request.HTTPError as e:
        body = e.read().decode()[:180]
        print(model + ': HTTP ' + str(e.code) + ' -> ' + body)
    except Exception as ex:
        print(model + ': ERROR -> ' + str(ex))
