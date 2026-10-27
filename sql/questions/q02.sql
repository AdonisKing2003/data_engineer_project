-- Câu 2 (Chung): Tỷ lệ từng kết quả cuối kỳ là bao nhiêu?
-- Đáp án chuẩn: Pass 37,9%; Withdrawn 31,2%; Fail 21,6%; Distinction 9,3%
SELECT final_result,
       COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM fact_enrollment
GROUP BY final_result
ORDER BY n DESC
