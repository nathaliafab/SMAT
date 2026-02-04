#!/usr/bin/env python3

import subprocess
import sys
import os
import json
import time
import logging
import shutil
from datetime import datetime
from pathlib import Path

# Configurações múltiplas para execução sequencial
MULTI_CONFIGS = [
    {
        "name": "ZeroShot_T00_S123",
        "prompt_template": "zero_shot",
        "temperature": 0,
        "seed": 123
    },
    {
        "name": "OneShot_T70_S123",
        "prompt_template": "one_shot",
        "temperature": 0.7,
        "seed": 123
    },
    {
        "name": "ZeroShot_T70_S123", 
        "prompt_template": "zero_shot",
        "temperature": 0.7,
        "seed": 123
    },
    {
        "name": "OneShot_T00_S123",
        "prompt_template": "one_shot",
        "temperature": 0,
        "seed": 123
    }
]

# Configuração de logging simples
def setup_simple_logging():
    """Configura logging básico mas eficaz"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"smat_execution_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return log_file

# Gerenciamento simples de progresso
class SimpleProgressManager:
    def __init__(self):
        self.checkpoint_dir = Path("checkpoints")
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.session_id = f"smat_{int(time.time())}"
        self.checkpoint_file = self.checkpoint_dir / f"progress_{self.session_id}.json"
        self.progress = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "configurations": {},  # {"config_name": {"completed_targets": [], "failed_targets": []}}
            "completed_scenarios": [],  # Manter para compatibilidade
            "failed_scenarios": [],
            "current_scenario": None
        }
        self.last_save_time = 0  # Controle de frequência de salvamento
    
    def save_progress(self, force=False):
        """Salva progresso atual (apenas a cada 10 minutos, exceto se force=True)"""
        current_time = time.time()
        
        # Salva apenas a cada 10 minutos (600 segundos) ou se forçado
        if not force and (current_time - self.last_save_time) < 600:
            return
            
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.progress, f, indent=2)
            
            self.last_save_time = current_time
            
            # Conta targets totais por configuração
            total_targets = sum(
                len(config_data.get('completed_targets', [])) + len(config_data.get('failed_targets', []))
                for config_data in self.progress['configurations'].values()
            )
            
            logging.info(f"Progresso salvo: {len(self.progress['completed_scenarios'])} cenários, {total_targets} targets processados")
        except Exception as e:
            logging.error(f"Erro ao salvar progresso: {e}")
    
    def add_completed(self, scenario_name):
        """Adiciona cenário concluído (compatibilidade)"""
        if scenario_name not in self.progress["completed_scenarios"]:
            self.progress["completed_scenarios"].append(scenario_name)
            self.save_progress(force=True)
    
    def add_failed(self, scenario_name):
        """Adiciona cenário que falhou (compatibilidade)"""
        if scenario_name not in self.progress["failed_scenarios"]:
            self.progress["failed_scenarios"].append(scenario_name)
            self.save_progress(force=True)
    
    def set_current(self, scenario_name):
        """Define cenário atual"""
        self.progress["current_scenario"] = scenario_name
        self.save_progress(force=True)
    
    def add_completed_target(self, config_name, target_info):
        """Adiciona target específico concluído para uma configuração"""
        if config_name not in self.progress["configurations"]:
            self.progress["configurations"][config_name] = {
                "completed_targets": [],
                "failed_targets": [],
                "start_time": datetime.now().isoformat()
            }
        
        target_key = f"{target_info['class']}.{target_info['method']}"
        if target_key not in self.progress["configurations"][config_name]["completed_targets"]:
            self.progress["configurations"][config_name]["completed_targets"].append(target_key)
            self.save_progress(force=True)  # Força salvamento em eventos importantes
            logging.info(f"Target concluído: {config_name} -> {target_key}")
    
    def add_failed_target(self, config_name, target_info, error=None):
        """Adiciona target que falhou para uma configuração"""
        if config_name not in self.progress["configurations"]:
            self.progress["configurations"][config_name] = {
                "completed_targets": [],
                "failed_targets": [],
                "start_time": datetime.now().isoformat()
            }
        
        target_key = f"{target_info['class']}.{target_info['method']}"
        failure_info = {
            "target": target_key,
            "error": str(error) if error else "Unknown error",
            "timestamp": datetime.now().isoformat()
        }
        
        self.progress["configurations"][config_name]["failed_targets"].append(failure_info)
        self.save_progress(force=True)  # Força salvamento em eventos importantes
        logging.error(f"Target falhou: {config_name} -> {target_key}: {error}")
    
    def get_config_progress(self, config_name):
        """Retorna progresso de uma configuração específica"""
        if config_name not in self.progress["configurations"]:
            return {"completed_targets": [], "failed_targets": []}
        return self.progress["configurations"][config_name]
    
    def get_summary(self):
        """Retorna resumo do progresso"""
        completed = len(self.progress["completed_scenarios"])
        failed = len(self.progress["failed_scenarios"])
        
        # Contagem detalhada por configuração
        config_summary = {}
        for config_name, config_data in self.progress["configurations"].items():
            completed_targets = len(config_data.get("completed_targets", []))
            failed_targets = len(config_data.get("failed_targets", []))
            config_summary[config_name] = {
                "completed_targets": completed_targets,
                "failed_targets": failed_targets,
                "targets": config_data.get("completed_targets", []) + [f["target"] for f in config_data.get("failed_targets", [])]
            }
        
        return {
            "session_id": self.session_id,
            "completed": completed,
            "failed": failed,
            "configurations": config_summary,
            "current": self.progress["current_scenario"],
            "start_time": self.progress["start_time"]
        }
    
    @classmethod
    def load_session(cls, session_id):
        """Carrega sessão existente"""
        checkpoint_dir = Path("checkpoints")
        checkpoint_file = checkpoint_dir / f"progress_{session_id}.json"
        
        if not checkpoint_file.exists():
            logging.error(f"Sessão não encontrada: {session_id}")
            return None
        
        try:
            with open(checkpoint_file, 'r') as f:
                progress_data = json.load(f)
            
            manager = cls()
            manager.session_id = session_id
            manager.checkpoint_file = checkpoint_file
            manager.progress = progress_data
            manager.last_save_time = 0  # Inicializa controle de salvamento
            
            logging.info(f"Sessão carregada: {session_id}")
            return manager
        except Exception as e:
            logging.error(f"Erro ao carregar sessão: {e}")
            return None
    
    @classmethod
    def list_sessions(cls):
        """Lista sessões disponíveis"""
        checkpoint_dir = Path("checkpoints")
        if not checkpoint_dir.exists():
            return []
        
        sessions = []
        for file in checkpoint_dir.glob("progress_*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                sessions.append({
                    'id': data['session_id'],
                    'start_time': data['start_time'],
                    'completed': len(data.get('completed_scenarios', [])),
                    'failed': len(data.get('failed_scenarios', []))
                })
            except:
                continue
        
        return sorted(sessions, key=lambda x: x['start_time'], reverse=True)

def update_env_config(config_update):
    """Atualiza o arquivo env-config.json com nova configuração"""
    env_config_path = Path("SMAT/nimrod/tests/env-config.json")
    
    # Faz backup do original
    backup_path = env_config_path.with_suffix('.json.backup')
    if not backup_path.exists():
        shutil.copy2(env_config_path, backup_path)
    
    # Carrega configuração atual
    with open(env_config_path, 'r') as f:
        config = json.load(f)
    
    # Atualiza configurações globais
    if 'prompt_template' in config_update:
        config['prompt_template'] = config_update['prompt_template']
    
    # Atualiza configurações da API para todos os modelos
    if 'temperature' in config_update or 'seed' in config_update:
        for model_key in config.get('api_params', {}):
            if 'temperature' in config_update:
                config['api_params'][model_key]['temperature'] = config_update['temperature']
            if 'seed' in config_update:
                config['api_params'][model_key]['seed'] = config_update['seed']
    
    # Salva configuração atualizada
    with open(env_config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logging.info(f"Configuração atualizada: {config_update['name']}")

def restore_env_config():
    """Restaura configuração original do backup"""
    env_config_path = Path("SMAT/nimrod/tests/env-config.json")
    backup_path = env_config_path.with_suffix('.json.backup')
    
    if backup_path.exists():
        shutil.copy2(backup_path, env_config_path)
        logging.info("Configuração original restaurada")

def run_smat(progress_manager, max_retries=2, config_name="default"):
    """Executa SMAT com retry básico e checkpoints"""
    
    
    try:
        # Configura ambiente
        smat_dir = Path(__file__).parent / "SMAT"
        os.environ['PYTHONPATH'] = str(smat_dir)
        if 'JAVA_HOME' not in os.environ:
            os.environ['JAVA_HOME'] = "/usr/lib/jvm/java-8-openjdk-amd64"
        
        logging.info(f"Iniciando SMAT - Sessão: {progress_manager.session_id} - Config: {config_name}")
        logging.info(f"PYTHONPATH: {os.environ['PYTHONPATH']}")
        
        # Executa SMAT
        
        for attempt in range(max_retries + 1):
            try:
                logging.info(f"Tentativa {attempt + 1}/{max_retries + 1}")
                
                # Inicia processo SMAT
                process = subprocess.Popen([
                    sys.executable, "-m", "nimrod"
                ], cwd=smat_dir)
                
                # Monitora processo enquanto executa
                while process.poll() is None:
                    time.sleep(30)  # Verifica a cada 30 segundos
                    progress_manager.save_progress()  # Tenta salvar (só salva a cada 10 min)
                
                # Verifica código de retorno
                if process.returncode == 0:
                    logging.info("SMAT executado com sucesso")
                    break
                else:
                    raise subprocess.CalledProcessError(process.returncode, "nimrod")
                
            except subprocess.CalledProcessError as e:
                logging.error(f"SMAT falhou (tentativa {attempt + 1}): código {e.returncode}")
                
                if attempt < max_retries:
                    delay = 60 * (attempt + 1)  # 60s, 120s, etc.
                    logging.info(f"Aguardando {delay}s antes da próxima tentativa...")
                    time.sleep(delay)
                else:
                    logging.error("SMAT falhou após todas as tentativas")
                    return False
            
            except KeyboardInterrupt:
                logging.info("Execução interrompida pelo usuário")
                progress_manager.save_progress()
                return False
        
        # Executa gráficos se disponível
        graphics_script = Path(__file__).parent / "graficos_metricas.py"
        if graphics_script.exists():
            try:
                logging.info("Gerando gráficos...")
                subprocess.run([sys.executable, str(graphics_script)], check=True)
                logging.info("Gráficos gerados com sucesso")
            except Exception as e:
                logging.warning(f"Erro ao gerar gráficos: {e}")
        
        return True
        
    except Exception as e:
        logging.error(f"Erro inesperado: {e}")
        return False
    finally:
        progress_manager.save_progress(force=True)

def load_targets_from_input():
    """Carrega lista de targets do input-smat.json"""
    try:
        input_file = Path("input-smat.json")
        if not input_file.exists():
            logging.warning("input-smat.json não encontrado")
            return []
        
        with open(input_file) as f:
            data = json.load(f)
        
        targets = []
        for scenario in data:
            for class_name, methods in scenario.get("targets", {}).items():
                for method_item in methods:
                    if isinstance(method_item, dict):
                        method_name = method_item.get("method", "")
                    else:
                        method_name = method_item
                    
                    targets.append({
                        "class": class_name,
                        "method": method_name,
                        "project": scenario.get("projectName", "unknown")
                    })
        
        return targets
    except Exception as e:
        logging.error(f"Erro ao carregar targets: {e}")
        return []

def verify_and_update_completed_targets(progress_manager, config_name, targets):
    """
    Verifica quais targets foram realmente concluídos baseado nos arquivos gerados
    e atualiza o progresso em tempo real
    """
    completed_count = 0
    output_base = Path("SMAT/output-test-dest/projects")
    
    try:
        if not output_base.exists():
            logging.debug("Diretório de output não existe ainda")
            return 0
        
        # Procura por pastas de output que correspondem ao config atual
        for project_dir in output_base.iterdir():
            if not project_dir.is_dir():
                continue
                
            # Verifica se há pastas com o padrão do modelo atual
            for model_dir in project_dir.iterdir():
                if not model_dir.is_dir():
                    continue
                    
                # Verifica se o nome da pasta contém as informações da configuração atual
                dir_name = model_dir.name
                if should_match_config(dir_name, config_name):
                    # Verifica cada target individualmente
                    for target in targets:
                        if check_target_completed(model_dir, target):
                            progress_manager.add_completed_target(config_name, target)
                            completed_count += 1
                            logging.debug(f"Target verificado como concluído: {target['class']}.{target['method']}")

    
    except Exception as e:
        logging.warning(f"Erro ao verificar targets concluídos: {e}")
    
    return completed_count

def should_match_config(dir_name, config_name):
    """Verifica se o nome do diretório corresponde à configuração atual"""
    return all(part in dir_name for part in config_name.split('_'))

def check_target_completed(model_dir, target):
    """Verifica se um target específico foi concluído com sucesso"""
    try:
        # Verifica se há arquivos .java gerados para este target
        llm_outputs_dir = model_dir / "llm_outputs"
        if not llm_outputs_dir.exists():
            return False
        
        # Procura por arquivos que contenham referências ao target
        class_simple_name = target['class'].split('.')[-1]
        method_name = target['method'].split('(')[0]
        
        target_pattern = f"*{class_simple_name}*{method_name}*"
        
        matching_files = list(llm_outputs_dir.glob(target_pattern))
        
        # Se encontrou arquivos, verifica se têm conteúdo válido
        for file_path in matching_files:
            if file_path.stat().st_size > 100:  # Arquivo não vazio (pelo menos 100 bytes)
                return True
        
        return False
        
    except Exception as e:
        logging.debug(f"Erro ao verificar conclusão do target {target['class']}.{target['method']}: {e}")
        return False

def run_smat_with_monitoring(progress_manager, config_name, targets):
    """Executa SMAT com verificação de progresso pós-execução"""
    return run_smat(progress_manager, config_name=config_name)

def run_smat_configs(progress_manager):
    """Executa múltiplas configurações sequencialmente"""
    total_configs = len(MULTI_CONFIGS)
    targets = load_targets_from_input()
    
    logging.info(f"Iniciando execução multi-configuração: {total_configs} configs, {len(targets)} targets")
    
    for i, config in enumerate(MULTI_CONFIGS, 1):
        logging.info(f"\n[CONFIG {i}/{total_configs}] Iniciando: {config['name']}")
        
        try:
            # Atualiza configuração
            update_env_config(config)
            
            # Executa SMAT com esta configuração e monitora progresso
            success = run_smat_with_monitoring(progress_manager, config['name'], targets)
            
            if success:
                progress_manager.add_completed(config['name'])
                
                # Verifica targets realmente concluídos
                completed_count = verify_and_update_completed_targets(progress_manager, config['name'], targets)
                logging.info(f"[CONFIG {i}/{total_configs}] OK Concluída: {config['name']} - {completed_count}/{len(targets)} targets verificados como concluídos")
            else:
                progress_manager.add_failed(config['name'])
                
                # Mesmo com falha, verifica se alguns targets foram concluídos
                completed_count = verify_and_update_completed_targets(progress_manager, config['name'], targets)
                logging.error(f"[CONFIG {i}/{total_configs}] ERRO Falhou: {config['name']} - {completed_count}/{len(targets)} targets parcialmente concluídos")
                
        except Exception as e:
            # Mesmo com exceção, verifica progresso parcial
            try:
                completed_count = verify_and_update_completed_targets(progress_manager, config['name'], targets)
                logging.error(f"[CONFIG {i}/{total_configs}] EXCEÇÃO: {config['name']} - {e} - {completed_count}/{len(targets)} targets parcialmente concluídos")
            except:
                logging.error(f"[CONFIG {i}/{total_configs}] EXCEÇÃO: {config['name']} - {e}")
            
            logging.error(f"[CONFIG {i}/{total_configs}] ERRO: {config['name']} - {e}")
            progress_manager.add_failed(config['name'])
        
        # Pausa entre configurações
        if i < total_configs:
            logging.info(f"Pausa de 30s antes da próxima configuração...")
            time.sleep(30)
    
    # Restaura configuração original
    restore_env_config()
    
    # Resumo final
    summary = progress_manager.get_summary()
    logging.info(f"Resumo final: {summary['completed']} concluídas, {summary['failed']} com falha")
    
    # Detalhes por configuração
    for config_name, config_data in summary['configurations'].items():
        completed_targets = config_data['completed_targets']
        failed_targets = config_data['failed_targets']
        logging.info(f"\n{config_name}:")
        logging.info(f"  Targets concluídos: {completed_targets}")
        logging.info(f"  Targets falharam: {failed_targets}")
        if config_data['targets']:
            logging.info(f"  Lista de targets: {', '.join(config_data['targets'])}")
    
    return summary['failed'] == 0

def main():
    """Função principal"""
    
    # Setup básico
    log_file = setup_simple_logging()
    
    # Argumentos simples
    resume_session = None
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--resume" and len(sys.argv) > 2:
            resume_session = sys.argv[2]
        elif sys.argv[1] == "--list":
            sessions = SimpleProgressManager.list_sessions()
            if sessions:
                print("Sessões disponíveis:")
                for session in sessions:
                    print(f"  {session['id']}: {session['start_time']} (Concluídos: {session['completed']}, Falhas: {session['failed']})")
            else:
                print("Nenhuma sessão encontrada")
            return 0
        elif sys.argv[1] in ["--help", "-h"]:
            print("Uso:")
            print("  python3 run_experiment.py           # Execução multi-configuração")
            print("  python3 run_experiment.py --resume SESSION_ID")
            print("  python3 run_experiment.py --list    # Lista sessões")
            return 0
    
    # Configura gerenciador de progresso
    if resume_session:
        progress_manager = SimpleProgressManager.load_session(resume_session)
        if not progress_manager:
            return 1
    else:
        progress_manager = SimpleProgressManager()
    
    logging.info(f"SMAT multi-config - Sessão: {progress_manager.session_id}")
    
    # Executa SMAT com múltiplas configurações
    success = run_smat_configs(progress_manager)
    
    # Resultado final
    if success:
        logging.info("Execução concluída com sucesso")
        return 0
    else:
        logging.error(f"Execução falhou. Use: python3 run_experiment.py --resume {progress_manager.session_id}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
