import { Card, EmptyState } from "../../components/ui";
import { IconMemory } from "../../components/icons";

export default function Memory() {
  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">الذاكرة</h1>
          <p className="rq-page-sub">
            تتبع المحادثات المشابهة والذاكرة المستخرجة من تفاعلات صفحتك مع العملاء.
          </p>
        </div>
      </div>
      <Card>
        <EmptyState
          icon={<IconMemory width={26} height={26} />}
          title="ستظهر الذاكرة بعد معالجة المحادثات"
          desc="عندما تكتمل خطوط أنابيب المعالجة، ستظهر هنا المحادثات المشابهة والأنماط المكتشفة."
        />
      </Card>
    </div>
  );
}
