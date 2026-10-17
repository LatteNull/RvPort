import { Component, ElementRef, ViewChild } from '@angular/core';
import { Location } from '@angular/common';
import { Router } from '@angular/router';

@Component({
  selector: 'app-platform-overview',
  templateUrl: './platform-overview.component.html',
  styleUrl: './platform-overview.component.css',
  standalone: false,
})
export class PlatformOverviewComponent {
  guideUrl = 'assets/markdown/platform-overview.md';

  @ViewChild('guideBody') guideBody?: ElementRef<HTMLElement>;
  private headingIdsAssigned = false;

  constructor(private router: Router, private location: Location) {}

  /** 返回上一页；若无历史则 fallback 到工具选择页 */
  goBack(): void {
    if (window.history.length > 1) {
      this.location.back();
    } else {
      this.router.navigate(['cardmodel']);
    }
  }

  onMarkdownLoaded(): void {
    this.assignHeadingIds();
  }

  /** 拦截正文内的链接：# 开头为页内锚点，/ 开头为应用内路由，都需手动处理避免被 hash 路由误判 */
  onBodyClick(event: MouseEvent): void {
    const anchor = (event.target as HTMLElement | null)?.closest('a');
    if (!anchor) {
      return;
    }
    const href = anchor.getAttribute('href') ?? '';
    if (!href) {
      return;
    }

    if (href.startsWith('#')) {
      if (href.length <= 1) {
        return;
      }
      event.preventDefault();
      if (!this.headingIdsAssigned) {
        this.assignHeadingIds();
      }
      const id = decodeURIComponent(href.slice(1));
      const target = this.guideBody?.nativeElement.querySelector(`#${CSS.escape(id)}`);
      if (target) {
        (target as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      return;
    }

    if (href.startsWith('/')) {
      event.preventDefault();
      this.router.navigate([href]);
    }
  }

  private assignHeadingIds(): void {
    const root = this.guideBody?.nativeElement;
    if (!root) {
      return;
    }
    const used = new Set<string>();
    root.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(heading => {
      const slug = this.slugify(heading.textContent ?? '');
      let id = slug;
      for (let i = 1; used.has(id); i++) {
        id = `${slug}-${i}`;
      }
      used.add(id);
      heading.id = id;
    });
    this.headingIdsAssigned = true;
  }

  private slugify(text: string): string {
    return text
      .toLowerCase()
      .replace(/[^\p{L}\p{N} -]/gu, '')
      .replace(/ /g, '-');
  }
}
