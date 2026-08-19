import { Card, EmptyState } from "../../components/ui";
import { IconTraining } from "../../components/icons";

export default function Training() {
  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">التدريب</h1>
          <p className="rq-page-sub">
            أنشئ مجموعات تدريب لتحسين ردود الذكاء الاصطناعي بناءً على تفاعلات صفحتك مع العملاء.
          </p>
        </div>
      </div>
      <Card>
        <EmptyState
          icon={<IconTraining width={26} height={26} />}
          title="لا محادثات معتمدة بعد"
          desc="عند اعتماد محادثات من صندوق المراجعة، ستظهر هنا مجموعات التدريب الجاهزة للتعلّم."
        />
      </Card>
    </div>
  );
}
