import { Card, EmptyState } from "../../components/ui";
import { IconAnalytics } from "../../components/icons";

export default function Analytics() {
  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">التحليلات</h1>
          <p className="rq-page-sub">
            راقب أداء صفحتك وتحليلات المحادثات وسلوك العملاء من مكان واحد.
          </p>
        </div>
      </div>
      <Card>
        <EmptyState
          icon={<IconAnalytics width={26} height={26} />}
          title="ستظهر التحليلات بعد تجميع بيانات كافية"
          desc="مع نمو عدد المحادثات والتفاعلات، ستظهر هنا الرسوم البيانية والرؤى التحليلية."
        />
      </Card>
    </div>
  );
}
