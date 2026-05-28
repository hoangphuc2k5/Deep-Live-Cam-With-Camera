from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
import io
import cv2
import numpy as np
from PIL import Image
from modules import imread_unicode
from modules.face_analyser import get_one_face
from modules.processors.frame.face_swapper import process_frame

app = FastAPI()

@app.post("/swap_face")
async def swap_face(source: UploadFile = File(...), target: UploadFile = File(...)):
    # Read uploaded files
    source_content = await source.read()
    target_content = await target.read()
    
    # Convert to numpy arrays
    source_img = np.array(Image.open(io.BytesIO(source_content)).convert('RGB'))
    source_img = cv2.cvtColor(source_img, cv2.COLOR_RGB2BGR)
    
    target_img = np.array(Image.open(io.BytesIO(target_content)).convert('RGB'))
    target_img = cv2.cvtColor(target_img, cv2.COLOR_RGB2BGR)
    
    # Get faces
    source_face = get_one_face(source_img)
    if not source_face:
        return {"error": "No face found in source image"}
    
    # Process
    result = process_frame(source_face, target_img)
    
    # Convert back to PIL for response
    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(result_rgb)
    
    # Save to bytes
    buf = io.BytesIO()
    result_pil.save(buf, format='PNG')
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)