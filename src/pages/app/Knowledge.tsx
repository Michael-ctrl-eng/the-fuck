import { Card, EmptyState } from "../../components/ui";
import { IconKnowledge } from "../../components/icons";

export default function Knowledge() {
  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">المعرفة</h1>
          <p className="rq-page-sub">
            أضف مصادر معرفة عملك لتحسين دقة الردود واستجابات الذكاء الاصطناعي.
          </p>
        </div>
      </div>
      <Card>
        <EmptyState
          icon={<IconKnowledge width={26} height={26} />}
          title="أضف مصدر معرفتك الأول"
          desc="اربط مستنداتك أو صفحة الأسئلة الشائعة لبدء بناء قاعدة معرفية ذكية."
        />
      </Card>
    </div>
  );
}
