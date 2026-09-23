from openai import AzureOpenAI 
from backend.app.config import settings  
client = AzureOpenAI(api_key=settings.azure_openai_api_key, api_version=settings.azure_openai_api_version, azure_endpoint=settings.azure_openai_endpoint)  
print('CHAT_DEPLOYMENT=', settings.azure_openai_chat_deployment)  
print('EMBED_DEPLOYMENT=', settings.azure_openai_embedding_deployment)  
try:  
    r = client.chat.completions.create(model=settings.azure_openai_chat_deployment, messages=[{'role': 'user', 'content': 'ping'}], max_tokens=5)  
    print('CHAT_OK=1')  
    print('CHAT_RESPONSE=', r.choices[0].message.content[:200])  
except Exception as e:  
    print('CHAT_OK=0')  
    print('CHAT_ERROR=', type(e).__name__)  
    print('CHAT_ERROR_MESSAGE=', str(e)[:500])  
try:  
    r = client.embeddings.create(model=settings.azure_openai_embedding_deployment, input='ping')  
    print('EMBED_OK=1')  
    print('EMBED_USAGE=', r.usage)  
except Exception as e:  
    print('EMBED_OK=0')  
    print('EMBED_ERROR=', type(e).__name__)  
    print('EMBED_ERROR_MESSAGE=', str(e)[:500])  
