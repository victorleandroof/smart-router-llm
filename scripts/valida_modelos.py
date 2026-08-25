import urllib.request, urllib.error, json, os
TOKEN=os.environ['LLM_GATEWAY_API_KEY']
URL=os.environ['LLM_GATEWAY_BASE_URL']
req=urllib.request.Request(f'{URL}/models', headers={'Authorization':f'Bearer {TOKEN}'})
try:
    data=json.loads(urllib.request.urlopen(req).read())['data']
except Exception as e:
    print(f'❌ Erro ao buscar modelos: {e}'); exit(1)
print(f'{len(data)} modelo(s) encontrado(s):\n')
for m in data:
    mid=m['id']
    body=json.dumps({'model':mid,'max_tokens':2,'messages':[{'role':'user','content':'hi'}]}).encode()
    r=urllib.request.Request(f'{URL}/chat/completions', data=body, headers={'Authorization':f'Bearer {TOKEN}','Content-Type':'application/json'})
    try:
        urllib.request.urlopen(r)
        print(f'✅ {mid}')
    except urllib.error.HTTPError as e:
        print(f'❌ {mid} (HTTP {e.code})')
    except Exception as e:
        print(f'❌ {mid} (erro: {e})')
