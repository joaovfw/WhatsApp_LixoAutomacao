# app.py (Código Atualizado)

from flask import Flask, request, jsonify
import requests
import json
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

# Configurações da API
WHAPI_TOKEN = os.getenv("WHAPI_TOKEN")
API_URL = os.getenv("API_URL")
PARTICIPANTS = [p.strip() for p in os.getenv("PARTICIPANTS", "Pessoa1,Pessoa2").split(',')]

# NOVO: ID do Grupo Alvo
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID") 

# --- Funções de Lógica do Rodízio (Inalteradas) ---

def load_data():
    """Carrega o índice do último responsável pelo lixo."""
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Inicia com o primeiro da lista se o arquivo não existir
        return {"last_person_index": -1} 

def save_data(data):
    """Salva o novo índice no arquivo data.json."""
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

def get_next_person_and_update():
    """Calcula e atualiza quem é o próximo a levar o lixo."""
    data = load_data()
    current_index = data.get("last_person_index", -1)
    
    # Próxima pessoa: Circularmente
    next_index = (current_index + 1) % len(PARTICIPANTS)
    next_person = PARTICIPANTS[next_index]
    
    # Atualiza o estado
    data["last_person_index"] = next_index
    save_data(data)
    
    return next_person

def who_is_next():
    """Retorna a pessoa que está atualmente na fila para levar o lixo (sem avançar)."""
    data = load_data()
    current_index = data.get("last_person_index", -1)
    
    # A pessoa da vez é a que vem DEPOIS do 'last_person_index' salvo
    next_index = (current_index + 1) % len(PARTICIPANTS)
    return PARTICIPANTS[next_index]

# --- Função de Envio de Mensagem (Resposta) ---

def send_whatsapp_message(chat_id, message_text):
    """Envia uma mensagem de volta ao WhatsApp usando a API do Whapi.cloud."""
    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": chat_id,
        "body": message_text
    }
    
    response = requests.post(f"{API_URL}/messages/text", headers=headers, json=payload)
    print(f"Resposta da API Whapi: {response.status_code} - {response.text}")
    return response.status_code

# --- Endpoint do Webhook (Recebimento de Mensagens) ---

@app.route("/webhook", methods=["POST"])
def webhook_handler():
    """Recebe e processa as mensagens de webhook do Whapi.cloud."""
    try:
        data = request.json
        print(f"Webhook recebido: {data}")

        for message_event in data.get("messages", []):
            if message_event.get("from_me"):
                continue  # Ignora mensagens enviadas pelo próprio bot

            chat_id = message_event.get("chat_id")
            
            # 🚨 VERIFICAÇÃO PRINCIPAL: O BOT SÓ PROCESSA MENSAGENS DESTE GRUPO
            if chat_id != TARGET_GROUP_ID:
                print(f"Mensagem ignorada. Não é do grupo alvo: {TARGET_GROUP_ID}")
                return jsonify({"status": "ignored", "reason": "Not target group"}), 200 # Resposta 200 OK para evitar reenvio
            
            # --- Lógica do Bot (Só executa se for o grupo alvo) ---
            text_body = message_event.get("text", {}).get("body", "").lower().strip()
            response_message = ""

            if text_body == "#lixo" or text_body == "#quem":
                pessoa_da_vez = who_is_next()
                response_message = f"🚨 A vez de levar o lixo é do(a) *{pessoa_da_vez}*!"
            
            elif text_body == "#levei" or text_body == "#check":
                pessoa_que_levou = get_next_person_and_update()
                proximo_agora = who_is_next()
                response_message = (
                    f"✅ Lixo levado por *{pessoa_que_levou}*! Parabéns! "
                    f"\n👉 O próximo(a) agora é o(a) *{proximo_agora}*."
                )

        
            
            if response_message:
                send_whatsapp_message(chat_id, response_message)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Erro no processamento do webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", 80)), debug=True)