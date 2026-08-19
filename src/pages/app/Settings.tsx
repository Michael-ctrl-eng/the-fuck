import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Card, CardHead, ConfirmDialog, EmptyState, Field, Input, Select, useToast } from "../../components/ui";
import { IconKey, IconTrash, IconUsers } from "../../components/icons";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { ROLE_LABELS, type Tone } from "../../lib/labels";
import { initials } from "../../lib/format";
import type { Member } from "../../lib/types";

const ROLE_TONES: Record<string, Tone> = {
  owner: "brand",
  admin: "info",
  moderator: "warn",
  viewer: "muted",
};

const ROLE_OPTIONS = [
  ["admin", "مدير"],
  ["moderator", "مشرف"],
  ["viewer", "مشاهد"],
] as const;

export default function Settings() {
  const { data: auth, role, orgId, switchOrg } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<string>("moderator");
  const [newOrgName, setNewOrgName] = useState("");
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [removeTarget, setRemoveTarget] = useState<Member | null>(null);

  const { data: members, isLoading } = useQuery({
    queryKey: ["members"],
    queryFn: () => api<Member[]>("/api/orgs/current/members"),
    staleTime: 30_000,
  });

  const isOwner = role === "owner";
  const canInvite = role === "owner" || role === "admin";

  const invite = useMutation({
    mutationFn: () =>
      api<Member>("/api/orgs/current/members", {
        method: "POST",
        body: { email: inviteEmail.trim(), role: inviteRole },
      }),
    onSuccess: () => {
      toast("success", "أُضيف العضو إلى المنظمة");
      setInviteEmail("");
      queryClient.invalidateQueries({ queryKey: ["members"] });
      queryClient.invalidateQueries({ queryKey: ["auth"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّرت الإضافة"),
  });

  const changeRole = useMutation({
    mutationFn: ({ membershipId, role: r }: { membershipId: string; role: string }) =>
      api(`/api/orgs/current/members/${membershipId}`, { method: "PATCH", body: { role: r } }),
    onSuccess: () => {
      toast("success", "تم تحديث الدور");
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر تحديث الدور"),
  });

  const remove = useMutation({
    mutationFn: (membershipId: string) =>
      api(`/api/orgs/current/members/${membershipId}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("success", "أُزيل العضو");
      setRemoveTarget(null);
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّرت الإزالة"),
  });

  const changePassword = useMutation({
    mutationFn: () => api("/api/auth/change-password", { method: "POST", body: { current_password: curPw, new_password: newPw } }),
    onSuccess: () => {
      toast("success", "تغيّرت كلمة المرور — أُلغيت الجلسات الأخرى");
      setCurPw("");
      setNewPw("");
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر التغيير"),
  });

  const createOrg = useMutation({
    mutationFn: () => api<{ id: string }>("/api/orgs", { method: "POST", body: { name: newOrgName.trim() } }),
    onSuccess: async (org) => {
      await switchOrg(org.id);
      toast("success", "أُنشئت المنظمة وانتقلت إليها");
      setNewOrgName("");
      queryClient.invalidateQueries({ queryKey: ["members"] });
    },
    onError: (err) => toast("error", err instanceof ApiError ? err.message : "تعذّر إنشاء المنظمة"),
  });

  const onInvite = (e: FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    invite.mutate();
  };

  const onChangePw = (e: FormEvent) => {
    e.preventDefault();
    if (newPw.length < 8) {
      toast("warn", "كلمة المرور الجديدة ٨ أحرف على الأقل");
      return;
    }
    changePassword.mutate();
  };

  const onCreateOrg = (e: FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    createOrg.mutate();
  };

  const currentOrg = auth?.orgs.find((o) => o.id === orgId);

  return (
    <div className="rq-page">
      <div className="rq-page-head">
        <div>
          <h1 className="rq-page-title">الفريق والإعدادات</h1>
          <p className="rq-page-sub">
            {currentOrg ? `منظمة «${currentOrg.name}» — دورك: ${ROLE_LABELS[currentOrg.role] ?? currentOrg.role}` : ""}
          </p>
        </div>
      </div>

      <div className="rq-grid rq-grid-2">
        {/* members */}
        <Card>
          <CardHead
            title="أعضاء المنظمة"
            actions={<Badge tone="brand">{members?.length ?? "—"} عضو</Badge>}
          />
          <div className="rq-card-body">
            {canInvite && (
              <form className="rq-row rq-mb rq-gap-2" style={{ alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={onInvite}>
                <Field className="rq-grow" style={{ minWidth: 180 }} label="بريد العضو (يجب أن يملك حسابًا)" htmlFor="invite_email">
                  <Input
                    id="invite_email"
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="member@example.com"
                    dir="ltr"
                    className="rq-text-end"
                  />
                </Field>
                <Field className="rq-grow" style={{ minWidth: 130 }} label="الدور" htmlFor="invite_role">
                  <Select
                    id="invite_role"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                  >
                    {ROLE_OPTIONS.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Button type="submit" variant="primary" size="sm" loading={invite.isPending}>
                  إضافة
                </Button>
              </form>
            )}

            {isLoading ? (
              <div className="rq-empty">
                <span className="rq-spinner" />
              </div>
            ) : !members || members.length === 0 ? (
              <EmptyState icon={<IconUsers width={26} height={26} />} title="لا أعضاء بعد" />
            ) : (
              <div className="rq-stack rq-gap-2">
                {members.map((m) => (
                  <div key={m.id} className="rq-panel" style={{ padding: "11px 14px" }}>
                    <div className="rq-row rq-gap-3">
                      <div className="rq-avatar">{initials(m.full_name || m.email)}</div>
                      <div className="rq-grow" style={{ minWidth: 0 }}>
                        <div className="rq-card-title" style={{ fontSize: 13.5 }}>
                          {m.full_name || m.email}
                        </div>
                        <div className="rq-xs rq-faint" style={{ direction: "ltr", textAlign: "right" }}>
                          {m.email}
                        </div>
                      </div>
                      {isOwner && m.role !== "owner" ? (
                        <Select
                          className="rq-xs"
                          style={{ width: "auto" }}
                          value={m.role}
                          onChange={(e) => changeRole.mutate({ membershipId: m.id, role: e.target.value })}
                          aria-label={`دور ${m.full_name}`}
                        >
                          {ROLE_OPTIONS.map(([v, l]) => (
                            <option key={v} value={v}>
                              {l}
                            </option>
                          ))}
                        </Select>
                      ) : (
                        <Badge tone={ROLE_TONES[m.role]}>{ROLE_LABELS[m.role]}</Badge>
                      )}
                      {isOwner && m.role !== "owner" && (
                        <Button variant="danger" size="sm" onClick={() => setRemoveTarget(m)} aria-label="إزالة">
                          <IconTrash width={14} height={14} />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <div className="rq-stack rq-gap-4">
          {/* password */}
          <Card>
            <CardHead title="كلمة المرور" />
            <div className="rq-card-body">
              <form className="rq-stack" onSubmit={onChangePw}>
                <Field label="كلمة المرور الحالية" htmlFor="cur">
                  <Input
                    id="cur"
                    type="password"
                    value={curPw}
                    onChange={(e) => setCurPw(e.target.value)}
                    autoComplete="current-password"
                  />
                </Field>
                <Field label="كلمة المرور الجديدة" htmlFor="new">
                  <Input
                    id="new"
                    type="password"
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                    placeholder="٨ أحرف على الأقل"
                    autoComplete="new-password"
                  />
                </Field>
                <Button type="submit" variant="primary" loading={changePassword.isPending}>
                  <IconKey width={16} height={16} /> تغيير كلمة المرور
                </Button>
              </form>
            </div>
          </Card>

          {/* orgs */}
          <Card>
            <CardHead title="المنظمات" />
            <div className="rq-card-body rq-stack rq-gap-2">
              {auth && auth.orgs.length > 1 && (
                  <div className="rq-stack rq-gap-2">
                  <div className="rq-label">التبديل بين المنظمات</div>
                  {auth.orgs.map((o) => (
                    <div key={o.id} className="rq-row rq-gap-2">
                      <Badge tone={o.id === orgId ? "brand" : "muted"} dot>
                        {o.name}
                      </Badge>
                      <span className="rq-xs rq-faint">{ROLE_LABELS[o.role]}</span>
                      {o.id !== orgId && (
                        <Button variant="ghost" size="sm" onClick={() => void switchOrg(o.id)}>
                          الانتقال
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <form className="rq-row rq-gap-2" style={{ alignItems: "flex-end", flexWrap: "wrap" }} onSubmit={onCreateOrg}>
                <Field className="rq-grow" style={{ minWidth: 180 }} label="إنشاء منظمة جديدة" htmlFor="new_org">
                  <Input
                    id="new_org"
                    value={newOrgName}
                    onChange={(e) => setNewOrgName(e.target.value)}
                    placeholder="اسم المنظمة الجديدة"
                  />
                </Field>
                <Button type="submit" variant="ghost" loading={createOrg.isPending}>
                  إنشاء
                </Button>
              </form>
            </div>
          </Card>

          <Card>
            <div className="rq-card-body rq-xs rq-faint" style={{ lineHeight: 1.9 }}>
              <strong className="rq-gold">ملاحظة أمان:</strong> تغيير كلمة المرور يُنهي جميع الجلسات
              الأخرى. جميع الإجراءات هنا مسجّلة في سجل التدقيق الخاص بالمنظمة.
            </div>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={removeTarget !== null}
        onClose={() => setRemoveTarget(null)}
        onConfirm={() => removeTarget && remove.mutate(removeTarget.id)}
        title="إزالة عضو"
        message={`إزالة «${removeTarget?.full_name || removeTarget?.email}» من المنظمة؟ لا يمكن التراجع عن هذا الإجراء.`}
        confirmLabel="إزالة"
        danger
        loading={remove.isPending}
      />
    </div>
  );
}
