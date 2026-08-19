import { Card, EmptyState } from "../../components/ui";
import { IconEval } from "../../components/icons";

export default function Evaluation() {
  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">التقييم</h1>
          <p className="rq-page-sub">
            قِس أداء نموذج الذكاء الاصطناعي وتتبع دقة الردود وجودتها بمرور الوقت.
          </p>
        </div>
      </div>
      <Card>
        <EmptyState
          icon={<IconEval width={26} height={26} />}
          title="سيظهر التقييم بعد معالجة أول مجموعة بيانات"
          desc="بعد تدريب نموذجك وبدء استخدامه، ستظهر هنا مقاييس الأداء وتقييمات الجودة."
        />
      </Card>
    </div>
  );
}
