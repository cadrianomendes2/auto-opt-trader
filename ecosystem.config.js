// ecosystem.config.js — Configuração PM2 para o Binary Options AI Dashboard
module.exports = {
  apps: [
    {
      name: "binary-opt-ai",
      script: "uvicorn",
      args: "src.main:app --host 0.0.0.0 --port 8000 --workers 1",
      interpreter: "python3",
      interpreter_args: "-m",
      cwd: "/Users/adrianomendes/Projects/binary-opt-ai",

      // Restart automático
      autorestart: true,
      watch: false,
      max_memory_restart: "512M",
      restart_delay: 3000,
      max_restarts: 20,

      // Logs
      log_file: "src/logs/combined.log",
      out_file: "src/logs/out.log",
      error_file: "src/logs/error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,

      // Variáveis de ambiente
      env: {
        NODE_ENV: "production",
        PYTHONPATH: "/Users/adrianomendes/Projects/binary-opt-ai",
        PYTHONUNBUFFERED: "1",
      },
      env_development: {
        NODE_ENV: "development",
        PYTHONPATH: "/Users/adrianomendes/Projects/binary-opt-ai",
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
