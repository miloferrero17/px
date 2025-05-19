#🧠 Conversational Engine
Motor conversacional basado en GPT-4, diseñado para ejecutar tareas rápidas, responder automáticamente y operar en modo WhatsApp. Soporta múltiples modos de interacción y lógica dinámica definida por el usuario.

#🧪 Modo de uso
1. Escribirle a este numero +14155238886 este mensaje join while-widely   
2. Seguir las instrucciones

#🚀 Características principales
  🔁 Integración con WhatsApp vía Twilio.
  🧠 Procesamiento de lenguaje natural usando OpenAI GPT-4.
  🧩 Lógica dinámica ejecutada desde base de datos o funciones definidas.
  🧵 Memoria conversacional persistente vía Supabase.
  📦 Vectorización semántica con embeddings + Pinecone.
  ☁️ Arquitectura serverless con Flask + AWS Lambda.
  🧭 Modos de conversación: Sherlock, FBI, Fofoqueo.

⚙️ Stack tecnológico
  Componente	        Tecnología
  Infraestructura	    AWS Lambda
  Backend	            Python + Flask
  Frontend	          WhatsApp (Twilio)
  Base de datos	      Supabase (REST API)
  Embeddings	        OpenAI (Ada)
  Vector DB	          Pinecone
  LLM	                OpenAI GPT-4

🧪 Modo de uso
  bash
  Copiar
  Editar
  # Clonar el repo
  git clone https://github.com/tuusuario/conversational-engine.git
  cd conversational-engine
  
  # Crear entorno virtual e instalar dependencias
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  
  # Configurar variables de entorno (.env)
  # OPENAI_API_KEY=...
  # SUPABASE_URL=...
  # ...
  
  # Ejecutar localmente
  python app/main.py
  🔌 Endpoints clave
  Método	Ruta	Descripción
  POST	/webhook	Recibe mensajes entrantes de WhatsApp
  POST	/test	Ejecuta lógica local con input de prueba
  GET	/status	Health check          

👤 Autor
Emilio Ferrero – [LinkedIn](https://www.linkedin.com/in/emilio-ferrero-87a64928/) – Consultor en AI y tecnología para salud, pagos y comercio exterior.
