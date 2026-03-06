import { cn } from '@/lib/utils';

type BrandLogoProps = {
  className?: string;
  logoClassName?: string;
  subtitleClassName?: string;
  showSubtitle?: boolean;
};

export default function BrandLogo({
  className,
  logoClassName,
  subtitleClassName,
  showSubtitle = true,
}: BrandLogoProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      <img
        src="/images/logo.png"
        alt="DXC"
        className={cn('h-7 w-auto', logoClassName)}
        loading="eager"
      />

      {showSubtitle ? (
        <span className={cn('text-dxc-peach text-xs font-body', subtitleClassName)}>
          Intelligent Analytics Platform
        </span>
      ) : null}
    </div>
  );
}