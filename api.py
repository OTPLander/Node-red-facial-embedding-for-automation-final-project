from flask import Flask, jsonify, request
from deepface import DeepFace
import base64
import os
import uuid

app = Flask(__name__)

@app.route('/embed_and_reconstruct', methods=['POST'])
def process_image():
    temp_filepath = f"temp_{uuid.uuid4().hex}.jpg"
    
    try:
        # 1. RECIBIR DATOS
        data = request.json
        byte_dict = data.get('image_bytes', {})
        
        if not byte_dict:
            return jsonify({"error": "No se recibieron bytes"}), 400
            
        # 2. RECONSTRUIR BINARIO
        length = len(byte_dict)
        byte_array = bytearray(length)
        for key, value in byte_dict.items():
            byte_array[int(key)] = value
            
        # 3. GENERAR BASE64 (Para el Dashboard)
        base64_encoded = base64.b64encode(byte_array).decode('utf-8')
        base64_string = f"data:image/jpeg;base64,{base64_encoded}"
        
        # 4. GUARDAR TEMPORALMENTE (Para DeepFace)
        with open(temp_filepath, 'wb') as f:
            f.write(byte_array)
            
        # 5. EXTRAER EMBEDDING
        # enforce_detection=False es vital para el dataset LFW
        objs = DeepFace.represent(img_path=temp_filepath, model_name="Facenet", enforce_detection=False)
        vector = objs[0]["embedding"]
        
        # 6. LIMPIEZA
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
            
        # 7. DEVOLVER AMBOS RESULTADOS
        return jsonify({
            "status": "success",
            "imagen_base64": base64_string,
            "embedding": vector
        })
        
    except Exception as e:
        print(f"Error procesando: {e}")
        # Asegurarnos de borrar la imagen si algo falla a medias
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)