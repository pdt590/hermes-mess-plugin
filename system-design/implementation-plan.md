# Messenger Plugin Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task in the current session. No subagents unless the user selects delegation.

**Goal:** Cung cấp Hermes platform plugin nhận tin Facebook qua ManyChat và gửi phản hồi AI về đúng contact.

**Architecture:** aiohttp webhook ghi sự kiện vào SQLite trước khi trả 202. Worker chuyển sự kiện thành MessageEvent; Hermes gateway sở hữu authorization, session và AI; adapter gửi văn bản qua ManyChat.

**Tech Stack:** Python theo runtime Hermes hiện cài, aiohttp, SQLite, pytest và pytest-asyncio.

**Spec:** [implementation-spec.md](implementation-spec.md), đã được người dùng duyệt ngày 2026-10-22.

**Kết quả thực hiện:** cả 5 task đã triển khai; 33 test thành công với runtime Hermes thật, không skip. Kiểm chứng và các quyết định điều chỉnh nằm trong [progress.md](progress.md). Facebook/ManyChat end-to-end thật chưa chạy vì chưa có credential và flow; không tự thay đổi gateway đang hoạt động.

## Global Constraints

- Không sửa Hermes core hoặc tự thay đổi cấu hình gateway đang chạy.
- Một kết nối ManyChat/Fanpage trên mỗi adapter; phiên bản đầu chỉ hỗ trợ văn bản và luồng bất đồng bộ.
- Không cần credential thật cho bộ kiểm thử tự động.
- Không ghi token thật, database hoặc file .env vào Git.
- Không hứa exactly-once; không coi HTTP 202 là giao tin thành công.

## Review Focus

- `handle_message()` của Hermes hiện cài trả về sau khi tạo background task: không coi lần return đó là AI xử lý xong; xác minh completion hooks trước khi chọn điểm cập nhật SQLite.
- Tiến trình bị ngắt giữa gửi và ghi trạng thái có thể tạo phản hồi trùng; phải ghi rõ giới hạn và không tự retry các lần gửi có kết quả không xác định.
- Contact khác nhau không dùng chung session; khách gửi `/...` không được cấp quyền quản trị gateway qua webhook.
- Cùng message ID với nội dung khác phải trả 409; thiếu message ID không được gộp các tin giống nhau.
- Shutdown, lỗi bind port và lỗi gateway không được làm mất sự kiện đã được trả 202 hoặc để lại tài nguyên mở.

## Task 1: Cấu hình và durable inbox

**Files:** `config.py`, `store.py`, `.gitignore`, `tests/test_config.py`, `tests/test_store.py`.

**Interfaces:** `Settings.from_platform(config)`; `Inbox(path, capacity, retention_seconds)`; `enqueue(payload)` trả receipt có ID và cờ duplicate; `claim()`, `complete(id)`, `fail(id, reason)`, `recover()`, `prune()`, `close()`.

- [x] Viết test cấu hình thiếu token/secret, giới hạn số không hợp lệ và ưu tiên cấu hình profile; xác nhận fail trước khi triển khai.
- [x] Viết test SQLite: enqueue rồi mở lại vẫn đọc được; duplicate không tạo hàng mới; khác payload gây conflict; thiếu ID tạo hai hàng; đầy hàng đợi bị từ chối; prune không xóa hàng chờ.
- [x] Chạy test, xác nhận fail do chưa có tính năng.
- [x] Triển khai schema có transaction, trạng thái và timestamp; dùng đường dẫn dữ liệu cấu hình được, không lưu trong source mặc định.
- [x] Chạy lại test task 1 và kiểm tra rollback khi admission lỗi.

## Task 2: Webhook HTTP

**Files:** `webhook.py`, `tests/test_webhook.py`.

**Interfaces:** `create_app(settings, inbox, wake_worker)` trả `aiohttp.web.Application`; sử dụng Settings và Inbox từ task 1.

- [x] Viết test qua aiohttp test server: secret sai/thiếu → 401; body quá lớn → 413; JSON sai, boolean ID, channel sai, message rỗng → 400; payload hợp lệ → 202 sau khi persist; echo → ignored; duplicate → accepted; conflict → 409; đầy → 503.
- [x] Xác nhận test fail rồi triển khai validation với giới hạn body 64 KiB, message 10.000 ký tự, contact ID là chuỗi chữ số ASCII hoặc số nguyên dương; không nhận float/boolean.
- [x] Dùng so sánh secret constant-time, health endpoint tối thiểu, response không chứa nội dung khách hoặc secret.
- [x] Chạy lại test HTTP và task 1.

## Task 3: ManyChat client

**Files:** `manychat.py`, `tests/test_manychat.py`.

**Interfaces:** `ManyChatClient(session, token)`; `send_text(contact_id, text)` trả kết quả đã lọc dữ liệu nhạy cảm, gồm thành công, lỗi, độ chắc chắn và thông tin gửi từng phần.

- [x] Truy xuất schema chính thức ManyChat sendContent; xác minh subscriber_id, version, content/messages, giới hạn văn bản và status trong JSON. Lưu căn cứ trong tài liệu; không đoán schema khi Swagger không đọc được.
- [x] Viết test bằng HTTP server giả cho đúng Authorization/body, thành công, HTTP 200 báo API error, 401, 429/Retry-After, 5xx, timeout sau khi server nhận body, phản hồi không phải JSON và lỗi ở chunk sau.
- [x] Chạy test để xác nhận fail.
- [x] Triển khai endpoint HTTPS cố định cho production; dùng fake server chỉ trong test. Retry tối đa 3 lần với backoff hữu hạn cho lỗi được xác định an toàn; không retry trường hợp gửi không rõ kết quả. Chia văn bản theo giới hạn đã xác minh và không gửi lại các chunk đã thành công.
- [x] Chạy lại test client; kiểm tra không có token/body phản hồi thô trong lỗi trả về.

## Task 4: Hermes platform integration và vòng đời

**Files:** `plugin.yaml`, `__init__.py`, `adapter.py`, `tests/test_adapter.py`, `tests/test_plugin.py`.

**Interfaces:** `register(ctx)` đăng ký `messenger`; `MessengerAdapter(BasePlatformAdapter)` triển khai `connect`, `disconnect`, `send`, `get_chat_info`; `send` trả `SendResult` thật của Hermes.

- [x] Đọc plugin loader, completion callbacks và base adapter của Hermes cài tại `../../hermes-agent`; xác minh manifest entrypoint và chữ ký callback. Nếu API không hỗ trợ xác nhận hoàn tất, dùng trạng thái `dispatched` rõ nghĩa và ghi giới hạn crash recovery, không gọi là delivered.
- [x] Viết test register, cấu hình theo profile, kết nối và ngắt hai lần, lỗi bind port, shutdown đang xử lý, phục hồi pending, worker exception, hai contact có hai session khác nhau.
- [x] Test inbound dựng DM qua `build_source(chat_id=contact_id, user_id=contact_id, chat_type="dm")`, `allow_gateway_control=False`, không đặt internal hoặc role_authorized để bypass quyền.
- [x] Test không đánh dấu complete ngay khi `handle_message()` tạo task; chứng minh điểm completion dựa trên hợp đồng runtime thật. Test gửi lỗi không báo thành công, không tạo retry chồng giữa client và gateway.
- [x] Chạy test fail, triển khai adapter và đăng ký profile-scoped config helpers; secrets `MESSENGER_WEBHOOK_SECRET` và `MANYCHAT_API_TOKEN`, authorization qua `MESSENGER_ALLOWED_USERS` hoặc `MESSENGER_ALLOW_ALL_USERS`.
- [x] Chạy toàn bộ suite và smoke test import/registration với module Hermes thật; không chỉ xác minh bằng class giả.

## Task 5: Hướng dẫn sử dụng và nghiệm thu

**Files:** `README.md`, `.env.example`, `requirements-dev.txt`, cập nhật trạng thái spec/plan.

- [x] Bổ sung cách cài và enable plugin, cấu hình port mặc định 8788 trên host 0.0.0.0, HTTPS tunnel/reverse proxy, đường dẫn SQLite và chính sách retention/capacity.
- [x] Hướng dẫn ManyChat External Request: header secret, payload mẫu, ý nghĩa contact/message ID, cách chọn biến thực sự có trong flow, HTTP 202 và gửi phản hồi bằng API. Nêu điều kiện quyền API và messaging window cần xác minh trên tài khoản thật.
- [x] Hướng dẫn authorization, lệnh chạy test, ví dụ request bằng PowerShell không chứa token thật, phân biệt queued/dispatched/delivered và hướng xử lý lỗi.
- [x] Chạy `python -m pytest` với runtime có dependencies; chạy `python -m compileall` trên source; kiểm tra diff, file bí mật và artifact thừa.
- [x] Báo số test và kết quả smoke test thật; ghi rõ Facebook/ManyChat end-to-end chưa kiểm chứng nếu không có credentials/flow thật. Không enable hoặc restart gateway đang chạy ngoài phạm vi người dùng yêu cầu.

## Phương thức thực hiện đề xuất

Thực hiện trực tiếp trong phiên hiện tại (`Native`): các task phụ thuộc chặt vào cùng API gateway và việc đối chiếu runtime. Không tạo commit tự động hoặc thay đổi global Git config. Có thể dùng `git -c safe.directory=<workspace>` cho các lệnh kiểm tra chỉ đọc nếu sandbox user khác chủ repository.
