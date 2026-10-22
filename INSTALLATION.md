# Hướng dẫn cài đặt

Yêu cầu: Python 3.11+, Hermes có API `register_platform`, `BasePlatformAdapter.on_processing_complete` và `_send_retry_is_final`. Đã kiểm thử bằng source/runtime Hermes cài trên máy; chưa cam kết tương thích mọi phiên bản Hermes cũ.

1. Đặt toàn bộ thư mục plugin tại `<Hermes home>/plugins/messenger`. Trên máy hiện tại thư mục này đã đúng vị trí.
2. Chạy script cài đặt bên dưới bằng Python của Hermes. Script kiểm tra và chỉ cài `aiohttp` khi thiếu; kiểm tra/cài thêm `ruamel.yaml` để gộp YAML và giữ comment.
3. Script bổ sung các biến còn thiếu vào `.env`, tạo webhook secret ngẫu nhiên khi chưa có; thêm `messenger` vào `plugins.enabled` và bổ sung `platforms.messenger` trong `config.yaml`.
4. Điền `MANYCHAT_API_TOKEN`, cấu hình contact được phép trong `.env`, chép webhook secret sang ManyChat. Khi sẵn sàng vận hành, khởi động lại gateway theo cách bạn đang quản lý Hermes.

**Windows PowerShell**, tại thư mục plugin:

```powershell
.\setup.ps1
```

**Linux / shell POSIX**:

```sh
sh ./setup.sh
```

`setup.sh` cũng dùng được trong Git Bash trên Windows. Các script tìm Python trong `hermes-agent/venv`, `hermes-agent/.venv`, `venv` hoặc `.venv` bên trong Hermes home. Nếu Hermes được cài ở vị trí khác, chỉ rõ Python thực sự chạy Hermes:

```powershell
.\setup.ps1 -HermesPython 'C:\path\to\hermes\venv\Scripts\python.exe'
# Ghi vào một Hermes home/profile được chỉ định:
.\setup.ps1 -HermesPython 'C:\path\to\hermes\venv\Scripts\python.exe' -HermesHome 'D:\hermes-profile'
```

```sh
HERMES_PYTHON="$HOME/hermes-agent/venv/bin/python" sh ./setup.sh
HERMES_PYTHON="$HOME/hermes-agent/venv/bin/python" HERMES_HOME="$HOME/custom-hermes" sh ./setup.sh
```

Mặc định file đích là `%LOCALAPPDATA%\hermes\.env` và `config.yaml` trên Windows, `~/.hermes/.env` và `config.yaml` trên Linux. `HERMES_HOME` hoặc tham số `-HermesHome` / `--hermes-home` chọn thư mục khác. Script in đường dẫn Python và thư mục đích, không in giá trị secret.

Script giữ nguyên mọi giá trị đã có, chỉ thêm khóa thiếu; chạy lại không chèn trùng. Mỗi file thay đổi được sao lưu thành `<tên file>.bak.<timestamp>` trước khi ghi thay thế. YAML sai cấu trúc bị từ chối trước khi ghi cả hai file. Không chạy script đồng thời với thao tác chỉnh/lưu cấu hình Hermes khác. Biến môi trường có sẵn trong shell được dùng cho các khóa `.env` mới; nếu chưa có, API token và allowlist được để trống, allow-all mặc định `false`. Các cấu hình `enabled: false` hoặc `plugins.disabled` có sẵn vẫn được giữ lại; kiểm tra và bật plugin bằng `hermes plugins enable messenger` nếu trước đó đã chủ động tắt. Script không tự restart Hermes.

Cấu hình platform được bổ sung khi chưa có:

```yaml
plugins:
  enabled:
    - messenger

platforms:
  messenger:
    enabled: true
    extra:
      host: 0.0.0.0
      port: 8788
      capacity: 1000
      retention_seconds: 604800
      timeout: 20
      processing_timeout: 600
```

Gộp vào các mục `plugins` và `platforms` sẵn có, giữ các plugin/platform khác. Khóa cấu hình trên là cấu trúc thực tế `GatewayConfig` của runtime đã kiểm tra; không thêm lớp `gateway:` bên ngoài. Biến môi trường theo profile ưu tiên hơn `extra`. Có thể đặt `extra.token` và `extra.webhook_secret` nếu quản lý secret qua YAML, nhưng không đưa chúng vào Git.

Nếu cài thủ công, dùng [.env.example](.env.example) và cấu hình trên; chạy `hermes plugins enable messenger` rồi khởi động lại gateway khi sẵn sàng.

Authorization dùng cơ chế Hermes: ban đầu đặt `MESSENGER_ALLOWED_USERS` bằng contact ID thử nghiệm và `MESSENGER_ALLOW_ALL_USERS=false`. Khi muốn phục vụ mọi khách hàng, chủ động đặt `MESSENGER_ALLOW_ALL_USERS=true`. Webhook secret xác thực ManyChat; allowlist quyết định ai được dùng agent. Plugin không tự bật quyền, không dùng trusted-inbound để bỏ qua authorization. Tin nhắn bắt đầu bằng `/` được chuyển như nội dung hội thoại, không mở gateway commands.

Chỉ chạy **một gateway/adapter** cho cùng database. Plugin chưa có cơ chế lease cho nhiều process. Giữ file SQLite trên ổ đĩa bền vững; không đặt trong thư mục tạm. Mặc định lưu tại `<active Hermes home>/plugin-data/messenger/inbox.sqlite`.

