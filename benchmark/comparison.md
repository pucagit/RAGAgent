# **CHƯƠNG 4: KẾT QUẢ THỰC NGHIỆM**

## **1. Mục tiêu**

Thực nghiệm nhằm **đánh giá hiệu năng truy hồi (retrieval performance)** của các mô hình embedding mã nguồn mở trong hệ thống **Retrieval-Augmented Generation (RAG)**, tập trung vào:

* So sánh độ chính xác giữa các mô hình theo loại câu hỏi;
* Phân tích đặc tính kỹ thuật ảnh hưởng đến khả năng biểu diễn ngữ nghĩa;
* Lựa chọn mô hình phù hợp cho môi trường RAG cục bộ trong lĩnh vực bảo mật.

---

## **2. Thiết lập**

* **Dataset:** [*Cybersecurity Attack Dataset*](https://huggingface.co/datasets/pucavv/Cybersecurity_Attack) (~18.29MB, ~14000 rows).
* **Công cụ:** PostgreSQL + `pgai Vectorizer`, chạy embedding qua Ollama.
* **Các mô hình thử nghiệm:** 8 mô hình embedding mã nguồn mở.
  
| Mô hình embedding               |    Parameters    | Dimensions |       Size | 
| ------------------------------- | ---------------- | ---------- | ---------- |
| **mxbai-embed-large**           |            	334M |       1024 |      670MB |
| **nomic-embed-text**            |            	137M |        768 |      274MB | 
| **bge-m3**                      |             567M |       1024 |      1.2GB |
| **qwen3-embedding:0.6b**        |             0.6B |       1024 |      639MB |
| **qwen3-embedding:4b**          |               4B |       2560 |      2.5GB |
| **embeddinggemma:300m**         |             300M |        768 |      622MB |
| **snowflake-arctic-embed:335m** |             335M |       1024 |      669MB |
| **granite-embedding:278m**      |             278M |        768 |      563MB |

* **Phân loại câu hỏi:**

| **Loại câu hỏi**          | **Mô tả**                                              | **Trọng tâm đánh giá**                                                                                            |
| ------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| **Câu hỏi ngắn**          | Câu hỏi đơn giản, trực tiếp, có độ dài dưới 10 từ      | Hiểu ngữ nghĩa (kiểm tra khả năng hiểu cơ bản)                                                                    |
| **Câu hỏi dài**           | Câu hỏi chi tiết, toàn diện, chứa các thông tin cụ thể | Truy hồi theo ngữ cảnh (kiểm tra khả năng xử lý câu hỏi sâu và nhiều chi tiết)                                    |
| **Câu hỏi trực tiếp**     | Đề cập đến nội dung được nêu rõ trong văn bản          | Hiểu ngữ nghĩa (kiểm tra khả năng truy hồi thông tin khớp chính xác)                                              |
| **Câu hỏi hàm ý**         | Câu hỏi dựa trên ngữ cảnh, đòi hỏi khả năng suy luận   | Truy hồi theo ngữ cảnh (kiểm tra khả năng hiểu ý nghĩa vượt ra ngoài nội dung hiển thị)                           |
| **Câu hỏi không rõ ràng** | Câu hỏi mơ hồ hoặc đa nghĩa                            | Kiểm tra cả hai tiêu chí đánh giá (khả năng của mô hình trong việc xử lý sự không chắc chắn và diễn giải ý nghĩa) |


* **Phương pháp:** 
  1. Chuẩn bị:
     - Dataset về Cybersecurity (~14000 rows)
     - Chọn ra 20 chunks ngẫu nhiên và tạo các câu hỏi dựa trên chúng
  2. Với mỗi model:
     - Vector hóa cấu hỏi, dataset với cùng chiến thuật (512 characters với 50 character overlap)
     - Thực hiện similarity search giữa các đoạn chunk của dataset và câu hỏi
     - Kiểm tra trong `top-K` kết quả có chứa đoạn chunk gốc không
  3. Tính toán hiệu năng:
     - Độ chính xác tổng thể
     - Độ chính xác dựa trên từng loại câu hỏi
---

## **3. Kết quả tổng hợp**

| Mô hình embedding               | Accuracy tổng thể |      Short |       Long |     Direct |    Implied |    Unclear |
| ------------------------------- | ----------------: | ---------: | ---------: | ---------: | ---------: | ---------: |
| **mxbai-embed-large**           |            57.96% |     45.00% |     93.75% |     53.75% |     73.75% |     25.00% |
| **nomic-embed-text**            |            59.20% |     43.75% |     95.00% |     55.00% |     73.75% |     30.00% |
| **bge-m3**                      |        **63.93%** | **55.00%** | **95.00%** | **61.25%** | **80.00%** | **30.00%** |
| **qwen3-embedding:0.6b**        |            53.48% |     28.75% |     91.25% |     50.00% |     75.00% |     23.75% |
| **qwen3-embedding:4b**          |            57.46% |     37.50% |     96.25% |     55.00% |     77.50% |     22.50% |
| **embeddinggemma:300m**         |            29.60% |      7.50% |     68.75% |     28.75% |     36.25% |      7.50% |
| **snowflake-arctic-embed:335m** |            38.06% |     30.00% |     68.75% |     35.00% |     46.25% |     11.25% |
| **granite-embedding:278m**      |            59.70% |     48.75% |     93.75% |     52.50% |     77.50% |     27.50% |

---

## **4. Phân tích kết quả**

### **4.1. Nhận xét tổng thể**

* **BGE-M3** đạt hiệu năng cao nhất (63.93%), thể hiện rõ khả năng biểu diễn ngữ nghĩa và khớp ngữ cảnh tốt.
  → Mô hình này sử dụng kiến trúc *multi-vector dense embedding*, được huấn luyện trên nhiều tập dữ liệu đối ngữ nghĩa (contrastive datasets) nên tạo ra không gian vector có tính phân biệt cao.

* **Nomic-embed-text** và **Granite-embedding** đạt hiệu năng ổn định (~59–60%), phản ánh thiết kế cân bằng giữa kích thước mô hình và khả năng hiểu ngữ nghĩa.
  → Hai mô hình này được tối ưu cho “general text representation”, phù hợp cho truy vấn đa lĩnh vực.

* **Qwen3 (0.6B và 4B)** cho thấy sự thiếu ổn định: mặc dù bản 4B lớn hơn, nhưng độ chính xác không vượt trội.
  → Nguyên nhân là vì Qwen3 tập trung huấn luyện cho sinh ngôn ngữ (language modeling) hơn là embedding retrieval.

* **Gemma và Arctic** có độ chính xác rất thấp, cho thấy **embedding space của chúng không được tối ưu hóa cho semantic retrieval** — phù hợp hơn với inference hoặc nhiệm vụ phân loại đơn giản.

---

### **4.2. Phân tích theo loại câu hỏi**

| Loại câu hỏi | Mô hình dẫn đầu     | Phân tích                                                                                   |
| ------------ | ------------------- | ------------------------------------------------------------------------------------------- |
| **Short**    | BGE-M3 (55%)        | Có khả năng encode từ vựng ngắn chính xác nhờ huấn luyện đa tầng với contrastive loss.      |
| **Long**     | Qwen3-4B (96.25%)   | Lợi thế ở biểu diễn ngữ cảnh dài, do dung lượng model lớn giúp giữ được thông tin dài hạn.  |
| **Direct**   | BGE-M3 (61.25%)     | Hiểu tốt nội dung xuất hiện rõ trong đoạn văn; embedding đa chiều giúp phân biệt chính xác. |
| **Implied**  | BGE-M3 (80%)        | Mạnh nhất về suy luận ngữ nghĩa – kết quả của việc huấn luyện trên NLI/STSB.                |
| **Unclear**  | Nomic, BGE-M3 (30%) | Dù mọi mô hình đều yếu ở truy vấn mơ hồ, BGE-M3 và Nomic ít bị nhiễu nhất.                  |

---

### **4.3. Giải thích lý thuyết**

1. **Cấu trúc huấn luyện contrastive learning** (ví dụ như của BGE, Nomic) giúp mô hình học cách phân tách các văn bản tương tự và khác biệt trong không gian vector → tăng độ chính xác truy hồi.
2. **Embedding dimension và số lượng cặp dữ liệu huấn luyện** ảnh hưởng trực tiếp đến khả năng khớp ngữ nghĩa. Mô hình lớn nhưng không được huấn luyện đúng cách (như Qwen3-4B) sẽ không tối ưu cho retrieval.
3. **Các mô hình nhỏ** có không gian vector hẹp hơn → dễ xảy ra hiện tượng “semantic collapse”, khiến câu hỏi tương tự khó được phân biệt.

---

### **4.4. Biểu đồ minh họa**

![Grouped Column Chart](evaluation_data/grouped_column.png)

#### 🔹 *Hình 4.1 – Biểu đồ cột nhóm (Grouped Column Chart)*

Biểu đồ cho thấy BGE-M3 nổi bật nhất ở tất cả nhóm câu hỏi, đặc biệt “Implied” và “Direct”.

---

## **5. Kết luận chương**

1. **BGE-M3** là mô hình **tối ưu nhất** cho tác vụ RAG cục bộ, đạt hiệu năng cao nhất ở cả độ chính xác tổng thể và từng loại truy vấn.
2. **Nomic-embed-text** và **Granite-278M** là lựa chọn nhẹ, thích hợp cho triển khai nội bộ với tài nguyên hạn chế.
3. **Qwen3-4B** có khả năng xử lý ngữ cảnh dài tốt, nhưng chưa vượt trội do không tối ưu đặc thù cho retrieval.
4. **Gemma và Arctic** chỉ nên dùng cho thử nghiệm hoặc mô phỏng pipeline RAG.
5. Với các ứng dụng RAG an ninh mạng, lựa chọn tốt nhất là **BGE-M3** hoặc **Nomic-embed-text**, đảm bảo cân bằng giữa hiệu năng, tốc độ và tính riêng tư dữ liệu.

## **6. Tham khảo**
https://www.tigerdata.com/blog/finding-the-best-open-source-embedding-model-for-rag