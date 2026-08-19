import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const defaults: Pick<IconProps, "xmlns" | "viewBox" | "width" | "height" | "aria-hidden" | "stroke" | "strokeLinecap" | "strokeLinejoin" | "fill"> = {
  xmlns: "http://www.w3.org/2000/svg",
  viewBox: "0 0 24 24",
  width: 20,
  height: 20,
  "aria-hidden": true,
  stroke: "currentColor",
  strokeLinecap: "square",
  strokeLinejoin: "miter",
  fill: "none",
};

/* ─── Navigation / Core ─── */

export function IconHome(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2.5}
        d="M3 12 L12 3 L21 12 M5 11 V20 H19 V11 M9 20 V14 H15 V20"
      />
    </svg>
  );
}

export function IconInbox(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M3 14 L3 20 H21 V14 M3 14 L8 9 L11 12 L16 7 L21 14 M8 9 V6 H16 V9"
      />
    </svg>
  );
}

export function IconChat(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M4 4 H20 V16 H8 L4 20 Z M8 9 H16 M8 13 H12"
      />
    </svg>
  );
}

export function IconPages(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M14 2 H4 V20 H20 V8 Z M14 2 V8 H20 M7 11 H17 M7 15 H17 M7 19 H13"
      />
    </svg>
  );
}

export function IconJobs(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 12 M10 10 H14 V14 H10 Z M12 2 V5 M12 19 V22 M2 12 V10 H5 V14 H2 M19 10 V14 H22 V10 H19 M3 3 H6 V6 H3 Z M18 3 H21 V6 H18 Z M3 18 H6 V21 H3 Z M18 18 H21 V21 H18 Z"
      />
    </svg>
  );
}

export function IconGear(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 12 M9 9 H15 V15 H9 Z M12 2 V6 M12 18 V22 M2 12 V9 H6 V15 H2 M18 9 V15 H22 V9 H18 M3 3 H6 V6 H3 Z M18 3 H21 V6 H18 Z M3 18 H6 V21 H3 Z M18 18 H21 V21 H18 Z"
      />
    </svg>
  );
}

export function IconLogout(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M9 3 H4 V21 H9 M9 12 H21 M16 8 L21 12 L16 16"
      />
    </svg>
  );
}

/* ─── Actions ─── */

export function IconSearch(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M10 3 H5 V8 H3 V16 H5 V21 H10 V16 H14 V21 H19 V16 H21 V8 H19 V3 H14 V8 H10 V3 Z M15 12 H19 M5 12 H9"
      />
    </svg>
  );
}

export function IconPlus(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2.5}
        d="M12 4 V20 M4 12 H20"
      />
    </svg>
  );
}

export function IconCheck(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2.5}
        d="M4 13 L8 17 L10 15 L8 13 L10 11 L16 5 L20 9 L10 19 L4 13 Z"
      />
    </svg>
  );
}

export function IconX(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2.5}
        d="M5 5 L10 10 M14 10 L19 5 M10 10 L5 19 L10 14 M14 10 L19 19 L14 14 M10 10 L14 14"
      />
    </svg>
  );
}

export function IconSend(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M3 12 L21 3 L12 21 L10 13 Z M10 13 L21 3"
      />
    </svg>
  );
}

export function IconRefresh(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M3 9 H7 V5 H9 V3 H15 V5 H17 V9 H21 M21 15 H17 V19 H15 V21 H9 V19 H7 V15 H3 M3 9 L6 12 M21 15 L18 12 M6 12 H3 V9 M18 12 H21 V15"
      />
    </svg>
  );
}

export function IconTrash(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M4 7 H20 M8 7 V4 H16 V7 M6 7 V20 H18 V7 M10 10 V17 M14 10 V17"
      />
    </svg>
  );
}

export function IconEdit(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M16 3 L21 8 L8 21 H3 V16 Z M14 5 L19 10"
      />
    </svg>
  );
}

export function IconLink(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M9 15 H7 A4 4 0 0 1 7 7 H9 M15 9 H17 A4 4 0 0 1 17 17 H15 M9 9 L15 15"
      />
    </svg>
  );
}

export function IconBell(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M8 17 H16 M5 12 H19 V10 C19 6 17 3 12 3 C7 3 5 6 5 10 Z M10 20 H14 V17 H10 Z"
      />
    </svg>
  );
}

/* ─── Arrows / Direction ─── */

export function IconArrowLeft(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2.5}
        d="M20 12 H4 M4 12 L10 6 M4 12 L10 18"
      />
    </svg>
  );
}

export function IconArrowRight(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2.5}
        d="M4 12 H20 M20 12 L14 6 M20 12 L14 18"
      />
    </svg>
  );
}

export function IconChevron(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2.5}
        d="M4 8 L12 16 L20 8"
      />
    </svg>
  );
}

/* ─── Content ─── */

export function IconEye(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M3 12 C5 6 9 3 12 3 C15 3 19 6 21 12 C19 18 15 21 12 21 C9 21 5 18 3 12 Z M10 10 H14 V14 H10 Z"
      />
    </svg>
  );
}

export function IconSpark(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 2 V8 M12 16 V22 M2 12 H8 M16 12 H22 M5 5 L9 9 M15 15 L19 19 M19 5 L15 9 M9 15 L5 19"
      />
    </svg>
  );
}

export function IconDialect(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M4 3 H20 V15 H12 L6 20 V15 H4 Z M8 7 H16 M8 11 H14"
      />
    </svg>
  );
}

export function IconShield(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 2 L4 6 V12 C4 17 8 21 12 22 C16 21 20 17 20 12 V6 Z"
      />
    </svg>
  );
}

export function IconDatabase(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M4 4 H20 V8 H4 Z M4 8 C4 8 4 12 12 12 C20 12 20 8 20 8 M4 12 C4 12 4 16 12 16 C20 16 20 12 20 12 M4 16 V20 H20 V16"
      />
    </svg>
  );
}

export function IconBrain(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 3 V21 M8 3 C4 3 3 6 3 9 C3 12 5 13 5 13 C5 13 3 14 3 17 C3 20 6 21 8 21 M16 3 C20 3 21 6 21 9 C21 12 19 13 19 13 C19 13 21 14 21 17 C21 20 18 21 16 21 M7 7 H10 M14 7 H17 M7 17 H10 M14 17 H17"
      />
    </svg>
  );
}

export function IconLock(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M7 10 V7 C7 4 9 2 12 2 C15 2 17 4 17 7 V10 M4 10 H20 V21 H4 Z M10 15 H14 V18 H10 Z"
      />
    </svg>
  );
}

export function IconUsers(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M9 10 C9 8 11 7 12 7 C13 7 15 8 15 10 C15 12 13 13 12 13 C11 13 9 12 9 10 Z M4 20 C4 16 8 14 12 14 C16 14 20 16 20 20 M17 8 C17 6 18 5 20 5 C22 5 23 7 22 10 M18 20 C18 17 20 16 21 15"
      />
    </svg>
  );
}

export function IconKey(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 21 L8 17 L8 13 L2 7 L7 2 L13 8 L13 12 L17 12 C20 12 22 10 22 7 C22 4 20 2 17 2 C14 2 12 4 12 7"
      />
    </svg>
  );
}

export function IconFile(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M14 2 H4 V22 H20 V8 Z M14 2 L20 8 M8 12 H16 M8 16 H16"
      />
    </svg>
  );
}

export function IconFlag(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M5 2 V22 M5 3 H17 V9 L13 7 L5 9"
      />
    </svg>
  );
}

export function IconGlobe(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 2 C6 2 2 7 2 12 C2 17 6 22 12 22 C18 22 22 17 22 12 C22 7 18 2 12 2 Z M3 12 H21 M12 2 C9 6 8 9 8 12 C8 15 9 18 12 22 M12 2 C15 6 16 9 16 12 C16 15 15 18 12 22"
      />
    </svg>
  );
}

export function IconWarning(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 2 L1 21 H23 Z M12 9 V14 M12 17 V18"
      />
    </svg>
  );
}

export function IconPause(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M7 3 V21 M17 3 V21"
      />
    </svg>
  );
}

export function IconPlay(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M6 3 L20 12 L6 21 Z"
      />
    </svg>
  );
}

export function IconReject(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 2 C6 2 2 6 2 12 C2 18 6 22 12 22 C18 22 22 18 22 12 C22 6 18 2 12 2 Z M8 8 L16 16 M16 8 L8 16"
      />
    </svg>
  );
}

/* ─── Additional Product Icons ─── */

export function IconMemory(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M8 2 H16 V4 H12 V7 H12 V10 H12 V14 H12 V17 H12 V20 H16 V22 H8 V20 H12 V17 H12 V14 H12 V10 H12 V7 H12 V4 H8 Z M8 4 V7 H4 V4 Z M16 4 V7 H20 V4 Z M8 17 V20 H4 V17 Z M16 17 V20 H20 V17 Z M4 10 H8 M16 10 H20 M4 14 H8 M16 14 H20"
      />
    </svg>
  );
}

export function IconKnowledge(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M4 3 H20 V20 H4 Z M4 3 L12 7 L20 3 M12 7 V20"
      />
    </svg>
  );
}

export function IconTraining(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M12 2 L2 8 L12 14 L22 8 Z M6 10 V16 C6 16 9 19 12 19 C15 19 18 16 18 16 V10 M12 14 L12 19"
      />
    </svg>
  );
}

export function IconEval(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M3 21 H21 V3 M3 21 L8 14 L12 17 L17 10 L21 13"
      />
    </svg>
  );
}

export function IconAnalytics(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M3 21 H21 V3 M5 17 H9 V11 M10 17 H14 V7 M15 17 H19 V13 M3 21 L3 3"
      />
    </svg>
  );
}

export function IconCommand(props: IconProps) {
  return (
    <svg {...defaults} {...props}>
      <path
        strokeWidth={2}
        d="M7 3 H5 V7 H7 M17 3 H19 V7 H17 M7 21 H5 V17 H7 M17 21 H19 V17 H17 M7 7 H17 V17 H7 Z M12 7 V17 M7 12 H17"
      />
    </svg>
  );
}
