import os
import subprocess

def fazer_deploy_site(slug_pasta: str):
    """
    Realiza o deploy automático da pasta do cliente gerado para a nuvem da Vercel usando npx.
    """
    caminho_pasta = os.path.join("clientes_gerados", slug_pasta)
    
    if not os.path.exists(caminho_pasta):
        print(f"❌ Erro: A pasta '{caminho_pasta}' não foi encontrada.")
        return None
        
    print(f"☁️ Iniciando deploy automático para a nuvem do site: {slug_pasta}...")
    
    try:
        # Usamos npx vercel para rodar diretamente sem depender de PATH global
        comando = f"npx vercel deploy --prod --yes --name {slug_pasta}"
        
        resultado = subprocess.run(
            comando, 
            shell=True, 
            cwd=caminho_pasta, 
            capture_output=True, 
            text=True
        )
        
        if resultado.returncode == 0:
            linhas = resultado.stdout.strip().split('\n')
            url_gerada = linhas[-1] if linhas else "URL não localizada na saída"
            print(f"✅ Deploy concluído com sucesso!")
            print(f"🌐 Link de Acesso Online: {url_gerada}")
            return url_gerada
        else:
            print(f"❌ Erro no deploy: {resultado.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Erro crítico ao executar o deploy: {e}")
        return None

if __name__ == "__main__":
    fazer_deploy_site("clinica-sorriso-perfeito")