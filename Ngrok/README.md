# Ngrok 目录

此目录用于存放 ngrok 可执行文件。

## 📥 下载 ngrok

1. 访问 [ngrok 官网](https://ngrok.com/download)
2. 下载适合你系统的版本（Linux 64-bit）
3. 将下载的 `ngrok` 文件放到此目录
4. 添加执行权限：
   ```bash
   chmod +x ngrok
   ```

## 🔑 配置 authtoken

```bash
cd Ngrok
./ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

详细配置说明请参考项目根目录的 [README.md](../README.md)。

## 📁 目录结构

```
Ngrok/
├── ngrok          # ngrok 可执行文件（需自行下载，已被 .gitignore 忽略）
└── README.md      # 本说明文件
```

## ⚠️ 注意

`ngrok` 可执行文件**不会**被提交到 Git 仓库（已在 `.gitignore` 中排除），需要自行下载。

