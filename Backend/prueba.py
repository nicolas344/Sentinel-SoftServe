from langfuse import Langfuse
import os
from dotenv import load_dotenv
load_dotenv()

lf = Langfuse(
    public_key=os.getenv('LANGFUSE_PUBLIC_KEY'),
    secret_key=os.getenv('LANGFUSE_SECRET_KEY'),
    host=os.getenv('LANGFUSE_HOST')
)

# Crear una traza de prueba
trace = lf.trace(name='test-sentinel')
trace.event(name='conexion-verificada', output='LangFuse OK')
lf.flush()
print('Conexion con LangFuse exitosa')
