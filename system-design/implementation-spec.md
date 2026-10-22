# Đặc tả plugin Messenger cho Hermes

Ngày: 2026-10-22. Trạng thái: đã duyệt và triển khai; 33 kiểm thử thành công với runtime Hermes thật. Chưa kiểm thử Fanpage/ManyChat end-to-end bằng credential thật. Xem `progress.md` cho các quyết định triển khai và kiểm chứng.

## Mục tiêu và phạm vi

Xây dựng plugin platform `messenger` trong thư mục hiện tại, không sửa Hermes core. ManyChat tiếp nhận tin nhắn Facebook và gọi webhook; Hermes gateway xử lý bằng agent đang cấu hình, duy trì hội thoại theo contact ID; adapter gửi kết quả về ManyChat. Không cần n8n, polling hoặc chạy một LLM riêng.

README.md và system-design/architecture.md là yêu cầu đầu vào. Đây là chatbot văn bản cho một kết nối ManyChat/Fanpage trên mỗi cấu hình adapter. Đính kèm, UI quản trị và nhiều Fanpage trong cùng một adapter nằm ngoài phiên bản đầu.

## Lựa chọn kiến trúc

1. **Khuyến nghị: platform adapter bất đồng bộ.** `register(ctx)` đăng ký platform; adapter kế thừa `BasePlatformAdapter`, nhận HTTP qua aiohttp, chuyển `MessageEvent` vào `handle_message`, thực hiện `send()` bằng ManyChat API. Tận dụng routing, session và agent của Hermes; trả HTTP 202 trước khi AI xử lý xong.
2. Đồng bộ qua External Request: dễ ánh xạ trường `reply` nhưng phụ thuộc timeout của ManyChat, không thích hợp tác vụ AI lâu.
3. Dịch vụ ngoài gọi Hermes API: tách triển khai nhưng thêm dịch vụ và cơ chế session; không tận dụng trực tiếp vòng đời platform plugin.

Chọn phương án 1 cho bản đầu. Luồng đồng bộ trong tài liệu kiến trúc là phương án thay thế, không đồng thời triển khai trong bản đầu.

## Hợp đồng webhook

`POST /webhooks/manychat`, JSON, header `X-Webhook-Secret` chứa secret cấu hình.

```json
{
  "contact_id": "123456789",
  "channel": "facebook",
  "message": "Cho tôi hỏi giá sản phẩm?",
  "message_id": "unique-inbound-id",
  "is_echo": false
}
```

Đây là hợp đồng do plugin định nghĩa; người triển khai ánh xạ các biến thực sự có trong ManyChat External Request. `contact_id` là ManyChat subscriber/contact ID, không tự coi là Facebook PSID. `message_id` tùy chọn; chỉ cam kết chống trùng khi có khóa ổn định. Không dùng nội dung tin nhắn làm khóa vì khách hàng có thể gửi cùng câu hai lần.

Kiểm tra secret bằng so sánh constant-time, giới hạn body, kiểu dữ liệu, độ dài nội dung, contact ID dạng số, channel facebook và cờ echo. Không chuyển kiểu boolean thành ID. Từ chối body sai, unauthorized hoặc quá lớn bằng mã 4xx; echo hợp lệ được bỏ qua. Không đưa secret hay nội dung khách hàng vào log.

Trả 202 chỉ sau khi ghi sự kiện vào SQLite. Hàng đợi đầy trả 503 để bên gọi có thể thử lại. Cùng message ID và cùng payload trả trạng thái đã nhận; cùng ID nhưng khác payload trả 409. `GET /healthz` chỉ trả trạng thái dịch vụ tối thiểu.

## Vòng đời và lưu trữ

`connect()` khởi tạo HTTP client, SQLite, worker và HTTP listener; thất bại phải dọn tài nguyên. `disconnect()` ngừng nhận, kết thúc hoặc hủy worker có kiểm soát, đóng server/client/database.

SQLite lưu inbox, khóa chống trùng và trạng thái xử lý; phục hồi sự kiện đang chờ khi khởi động. Một worker FIFO ở bản đầu giữ thứ tự tin nhắn. Mỗi contact được định danh thành DM riêng qua gateway để duy trì ngữ cảnh; dùng session của Hermes, không dựng lịch sử hội thoại riêng trong plugin.

Không hứa exactly-once: nếu tiến trình chết sau khi ManyChat nhận tin nhưng trước lúc ghi trạng thái, việc phục hồi có thể gửi lại. Giới hạn lưu trữ và thời hạn dọn bản ghi hoàn tất phải cấu hình được; không xóa bản ghi đang chờ.

## Gửi phản hồi và lỗi

ManyChat client sử dụng HTTPS, Bearer token, timeout hữu hạn và endpoint Facebook sendContent theo schema chính thức được kiểm tra ở bước triển khai. Chia văn bản dài theo giới hạn đã xác minh. Phân biệt HTTP lỗi với JSON báo lỗi dù HTTP 200.

Retry hữu hạn với backoff cho rate limit và lỗi tạm thời, tôn trọng Retry-After và không retry lỗi xác thực/validation. Không retry mù khi không xác định yêu cầu gửi đã được chấp nhận hay chưa. Lỗi gửi trả `SendResult(success=False, ...)` đã lọc dữ liệu nhạy cảm. Không coi webhook 202 là tin nhắn đã được gửi thành công.

Quyền người dùng sử dụng cơ chế authorization của Hermes. Tài liệu cấu hình nêu rõ lựa chọn allowlist hoặc cho phép mọi khách hàng; plugin không tự mở quyền hoặc sửa cấu hình Hermes toàn cục.

## Cấu trúc dự kiến

- `plugin.yaml`, `__init__.py`: manifest và đăng ký platform.
- `adapter.py`: vòng đời, MessageEvent, send và session routing.
- `config.py`: cấu hình, kiểm tra secret/token, giới hạn.
- `webhook.py`: HTTP và validation.
- `store.py`: SQLite inbox, deduplication, phục hồi.
- `manychat.py`: API client và phân loại lỗi.
- `tests/`: kiểm thử HTTP, storage, client và hợp đồng gateway.
- `.env.example`, tài liệu cài đặt và ManyChat Automation trong README.

Không ghi token thật, database hoặc file .env vào Git.

## Tiêu chí nghiệm thu

Kiểm thử xác thực, JSON lỗi, ID sai, echo, body quá lớn, deduplication và conflict; kiểm thử phục hồi SQLite và giới hạn hàng đợi; kiểm thử ManyChat thành công, lỗi HTTP, lỗi JSON, timeout và rate limit bằng server giả. Kiểm thử adapter đăng ký đúng API của Hermes cài trên máy, chuyển inbound vào gateway và gửi outbound tới đúng contact. Không cần credential thật cho bộ kiểm thử tự động.

Đọc nguồn Hermes hiện cài để xác minh chữ ký API trước khi viết adapter. Chạy kiểm thử và kiểm tra import; nếu có môi trường hỗ trợ, chạy smoke test nạp plugin bằng plugin manager thật. Chỉ gọi tích hợp Facebook thực tế thành công khi đã kiểm tra bằng tài khoản và flow ManyChat thật; nếu thiếu credential, báo riêng phần chưa kiểm chứng.

## Nguồn

- README.md và system-design/architecture.md trong repository.
- Hermes cài tại `../../hermes-agent`, đặc biệt `website/docs/developer-guide/adding-platform-adapters.md`.
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/adding-platform-adapters.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/plugins.md
- https://api.manychat.com/swagger#/
