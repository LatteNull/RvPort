import { Component, ElementRef, ViewChild } from '@angular/core';
import { Location } from '@angular/common';
import { Router } from '@angular/router';

@Component({
  selector: 'app-codemig-guide',
  templateUrl: './codemig-guide.component.html',
  styleUrl: './codemig-guide.component.css',
  standalone: false,
})
export class CodemigGuideComponent {
  guideUrl = 'assets/markdown/migration-tool-guide.md';

  @ViewChild('guideBody') guideBody?: ElementRef<HTMLElement>;
  private headingIdsAssigned = false;

  constructor(private location: Location, private router: Router) {}

  /** 返回上一页；若无历史则 fallback 到迁移工具主页 */
  goBack(): void {
    if (window.history.length > 1) {
      this.location.back();
    } else {
      this.router.navigate(['codemig']);
    }
  }

  /** markdown 渲染完成后，给所有标题补上与正文锚点一致的 id */
  onMarkdownLoaded(): void {
    this.assignHeadingIds();
  }

  /** 拦截正文内的 # 章节链接：hash 路由下 URL 片段已被路由占用，无法靠默认行为跳转，这里手动滚动 */
  onBodyClick(event: MouseEvent): void {
    const anchor = (event.target as HTMLElement | null)?.closest('a');
    if (!anchor) {
      return;
    }
    const href = anchor.getAttribute('href') ?? '';
    if (!href.startsWith('#') || href.length <= 1) {
      return;
    }
    // hash 路由下任何 # 片段都会被当成路由，必须一律阻止默认行为，避免 URL 被改坏跳到 404/登录
    event.preventDefault();
    if (!this.headingIdsAssigned) {
      this.assignHeadingIds();
    }
    const id = decodeURIComponent(href.slice(1));
    const target = this.guideBody?.nativeElement.querySelector(`#${CSS.escape(id)}`);
    if (target) {
      (target as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' });
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

  /** 复刻 GitHub 标题转 id 规则，使其与手册里手写的锚点（如 #1-简介、#46-任务快捷操作）一致 */
  private slugify(text: string): string {
    return text
      .toLowerCase()
      .replace(/[^\p{L}\p{N} -]/gu, '')
      .replace(/ /g, '-');
  }
}
