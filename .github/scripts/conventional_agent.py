import os
import time
import subprocess
from google import genai

def obtener_diff_actual():
    try:
        resultado_diff = subprocess.run(
            ['git', 'diff', 'HEAD~1', 'HEAD'],
            capture_output=True, text=True, check=True
        )
        return resultado_diff.stdout
    except Exception as e:
        return f"Error al obtener el diff: {str(e)}"

def generar_mensaje_con_ia(diff_texto):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("La variable de entorno GEMINI_API_KEY no está configurada.")

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Actúa como un agente experto en Conventional Commits y gobernanza de código. 
    Analiza el siguiente git diff y genera un mensaje de commit que cumpla estrictamente con esta norma:
    - Cabecera: tipo(ámbito opcional): descripción, en minúsculas, en imperativo, sin punto final y de 72 caracteres como máximo.
    - Tipos permitidos estrictamente: feat, fix, refactor, style, perf, docs, chore, build, ci, test.
    - Cuerpo y pie: Explica el qué y el porqué, separado por una línea en blanco de la cabecera. Si hay cambios incompatibles, añade '!' tras el tipo y especifica 'BREAKING CHANGE:' en el pie.
    
    Devuelve ÚNICAMENTE el texto final del commit con el formato correcto (Cabecera + línea en blanco + Cuerpo/pie si procede), sin bloques de código markdown ni explicaciones adicionales.
    
    Git Diff:
    {diff_texto}
    """
    
    # Intentos controlados con los tiempos de espera solicitados:
    # Intento 1 -> Falla -> Espera 5 minutos (300 segundos) -> Intento 2 -> Falla -> Espera 10 minutos (600 segundos) -> Intento 3 (Último)
    tiempos_espera = [300, 600] 
    max_intentos = len(tiempos_espera) + 1
    
    for intento in range(1, max_intentos + 1):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Aviso: Intento {intento}/{max_intentos} fallido al conectar con Gemini. Motivo: {str(e)}")
            
            if intento == max_intentos:
                raise RuntimeError("Se agotaron todos los reintentos (tras las esperas de 5 y 10 minutos) debido a la saturación de los servidores.")
            
            tiempo_actual_segundos = tiempos_espera[intento - 1]
            minutos = tiempo_actual_segundos // 60
            print(f"Esperando {minutos} minutos antes del siguiente intento para dejar que los servidores se desaturen...")
            time.sleep(tiempo_actual_segundos)

    raise RuntimeError("No se pudo generar el mensaje con la IA tras agotar los reintentos.")

def aplicar_amend_con_ia():
    try:
        # Evitar bucles infinitos si el commit ya cumple con la norma
        resultado_log = subprocess.run(['git', 'log', '-1', '--pretty=format:%s'], capture_output=True, text=True, check=True)
        ultimo_mensaje = resultado_log.stdout.strip()
        
        if ultimo_mensaje.startswith(('feat(', 'fix(', 'refactor(', 'style(', 'perf(', 'docs(', 'chore(', 'build(', 'ci(', 'test(')):
            print("El commit actual ya cumple con Conventional Commits. Omitiendo proceso.")
            return

        diff_texto = obtener_diff_actual()
        if not diff_texto.strip():
            print("No se encontraron cambios en el diff para analizar.")
            return

        print("Generando mensaje estructurado mediante IA con política de espera (5m y 10m)...")
        mensaje_completo = generar_mensaje_con_ia(diff_texto)

        # Actualizar el repositorio local y remoto con el nuevo mensaje
        subprocess.run(['git', 'add', '-A'], check=True)
        subprocess.run(['git', 'commit', '--amend', '-m', mensaje_completo], check=True)
        
        branch = os.getenv('GITHUB_REF_NAME', 'main')
        subprocess.run(['git', 'push', 'origin', f'HEAD:{branch}', '--force'], check=True)
        print("¡Historial normalizado y commit modificado con éxito!")
    except Exception as e:
        print(f"Error crítico en la ejecución del agente de IA: {str(e)}")

if __name__ == '__main__':
    aplicar_amend_con_ia()
    
