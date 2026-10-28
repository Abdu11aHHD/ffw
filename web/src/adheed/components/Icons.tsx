/** Inline SVG icon set. One stroke weight, one visual language.
 *  Icons are decorative: every one is paired with a text label. */

import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 22, ...rest }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    focusable: false,
    ...rest,
  };
}

export const HomeIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3.2 4.6 7.4v6.9c0 3 2.6 5.3 7.4 6.5 4.8-1.2 7.4-3.5 7.4-6.5V7.4Z" />
  </svg>
);

export const CalendarIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="3" />
    <path d="M3.5 9.5h17M8 3.5v3M16 3.5v3" />
    <circle cx="8.5" cy="13.5" r="1" fill="currentColor" stroke="none" />
    <circle cx="12" cy="13.5" r="1" fill="currentColor" stroke="none" />
    <circle cx="15.5" cy="13.5" r="1" fill="currentColor" stroke="none" />
    <circle cx="8.5" cy="17" r="1" fill="currentColor" stroke="none" />
    <circle cx="12" cy="17" r="1" fill="currentColor" stroke="none" />
  </svg>
);

export const LeafIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 21v-6.5" />
    <path d="M12 14.5c-3.6 0-6-2-6-5.2 2.9-1.3 6 .6 6 5.2Z" />
    <path d="M12 14.5c3.6 0 6-2 6-5.2-2.9-1.3-6 .6-6 5.2Z" />
    <path d="M12 9.6C12 6.4 13.4 4 15 3c.8 1.9.4 4.6-3 6.6Z" />
  </svg>
);

export const UserIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="8" r="3.6" />
    <path d="M4.8 20.2c.6-3.7 3.5-5.8 7.2-5.8s6.6 2.1 7.2 5.8" />
  </svg>
);

export const BellIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 3.3.8 5 1.7 6H4.8c.9-1 1.7-2.7 1.7-6Z" />
    <path d="M10 19.3a2.2 2.2 0 0 0 4 0" />
  </svg>
);

export const ChevronLeft = (p: IconProps) => (
  <svg {...base(p)}><path d="M14.5 5.5 8 12l6.5 6.5" /></svg>
);

export const ChevronRight = (p: IconProps) => (
  <svg {...base(p)}><path d="M9.5 5.5 16 12l-6.5 6.5" /></svg>
);

export const ChevronDown = (p: IconProps) => (
  <svg {...base(p)}><path d="M5.5 9 12 15.5 18.5 9" /></svg>
);

export const DropletIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3.4c0 0-5.6 6.1-5.6 9.8a5.6 5.6 0 0 0 11.2 0C17.6 9.5 12 3.4 12 3.4Z" />
    <path d="M9.6 13.8h4.8M12 11.4v4.8" />
  </svg>
);

export const ClipboardIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="5" y="4.5" width="14" height="16" rx="3" />
    <path d="M9 4.5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 4.5v1.2H9Z" />
    <path d="M8.8 11.5h6.4M8.8 15h4.4" />
  </svg>
);

export const PillIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="2.8" y="9" width="13" height="7.5" rx="3.75" transform="rotate(-20 2.8 9)" />
    <path d="M8.7 8.4 12 15.2" />
    <circle cx="17.6" cy="7.2" r="3.4" />
  </svg>
);

export const StethoscopeIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 3.5v4.2a3.6 3.6 0 0 0 7.2 0V3.5" />
    <path d="M4.6 3.5h2.2M12.1 3.5h2.2" />
    <path d="M9.6 11.3v2.1a4.8 4.8 0 0 0 9.6 0v-1.2" />
    <circle cx="19.2" cy="10.3" r="1.9" />
  </svg>
);

export const DocumentIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6 3.5h7l5 5v12H6Z" />
    <path d="M13 3.5v5h5M9 13h6M9 16.5h4" />
  </svg>
);

export const BedIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M3.5 8v10M3.5 13.5h17V18M20.5 13.5a4 4 0 0 0-4-4H10v4" />
    <circle cx="7" cy="11" r="1.8" />
  </svg>
);

export const UploadIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 16V4.8M8.2 8.4 12 4.6l3.8 3.8" />
    <path d="M4.5 15v3.2a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V15" />
  </svg>
);

export const CheckIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M5 12.5 9.8 17 19 7.5" /></svg>
);

export const CheckCircle = (p: IconProps) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="8.6" /><path d="M8.2 12.3 11 15l5-5.4" /></svg>
);

export const AlertIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 4.3 2.9 19.4h18.2Z" /><path d="M12 10v4" />
    <circle cx="12" cy="16.9" r="0.9" fill="currentColor" stroke="none" />
  </svg>
);

export const InfoIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="8.6" /><path d="M12 11v5.2" />
    <circle cx="12" cy="8" r="0.9" fill="currentColor" stroke="none" />
  </svg>
);

export const ClockIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="8.6" /><path d="M12 7.2V12l3.1 2" /></svg>
);

export const ShareIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="6.2" cy="12" r="2.3" /><circle cx="17.2" cy="6.2" r="2.3" /><circle cx="17.2" cy="17.8" r="2.3" />
    <path d="M8.3 10.9 15.1 7.3M8.3 13.1l6.8 3.6" />
  </svg>
);

export const TrashIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4.8 6.8h14.4M9.2 6.8V4.9h5.6v1.9M6.6 6.8l.9 12.3h9l.9-12.3" />
    <path d="M10.3 10.3v5.6M13.7 10.3v5.6" />
  </svg>
);

export const CloseIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M6 6l12 12M18 6 6 18" /></svg>
);

export const LabIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M10 3.5v6.1L5.3 17.6A2.3 2.3 0 0 0 7.3 21h9.4a2.3 2.3 0 0 0 2-3.4L14 9.6V3.5" />
    <path d="M8.7 3.5h6.6M7.4 14.8h9.2" />
  </svg>
);

export const HeartIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 19.8s-7.3-4.3-7.3-9.1A3.9 3.9 0 0 1 12 8.3a3.9 3.9 0 0 1 7.3 2.4c0 4.8-7.3 9.1-7.3 9.1Z" />
  </svg>
);

export const RangeIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3.2" y="9.4" width="17.6" height="5.2" rx="2.6" />
    <path d="M9 9.4v5.2M15 9.4v5.2M12 5.4v2.4M12 16.2v2.4" />
  </svg>
);

export const SparkIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3.6 13.7 9l5.4 1.7-5.4 1.7L12 17.8l-1.7-5.4L4.9 10.7 10.3 9Z" />
    <path d="M18.4 16.6l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7Z" />
  </svg>
);

export const ChartIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 19.3h16" /><path d="M7 19.3v-5M12 19.3V7.5M17 19.3v-8.4" />
  </svg>
);

export const QuestionIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="8.6" />
    <path d="M9.7 9.6a2.4 2.4 0 1 1 3.1 2.3c-.6.2-.8.7-.8 1.3v.4" />
    <circle cx="12" cy="16.4" r="0.9" fill="currentColor" stroke="none" />
  </svg>
);

export const RefreshIcon = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M19.3 11.3A7.3 7.3 0 0 0 6.4 7.6M4.7 12.7a7.3 7.3 0 0 0 12.9 3.7" />
    <path d="M19.3 6.5v4.8h-4.8M4.7 17.5v-4.8h4.8" />
  </svg>
);

export const SearchIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="11" cy="11" r="6.6" /><path d="M15.8 15.8 20 20" /></svg>
);

export const ICONS = {
  home: HomeIcon, calendar: CalendarIcon, leaf: LeafIcon, user: UserIcon,
  bell: BellIcon, glucose: DropletIcon, clipboard: ClipboardIcon, pill: PillIcon,
  stethoscope: StethoscopeIcon, document: DocumentIcon, bed: BedIcon,
  upload: UploadIcon, check: CheckIcon, alert: AlertIcon, info: InfoIcon,
  clock: ClockIcon, lab: LabIcon, heart: HeartIcon, range: RangeIcon,
  spark: SparkIcon, chart: ChartIcon, question: QuestionIcon,
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, ...rest }: IconProps & { name: IconName }) {
  const Cmp = ICONS[name] ?? InfoIcon;
  return <Cmp {...rest} />;
}
