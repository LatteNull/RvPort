import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

// Polyfill for crypto.randomUUID() if not available
if (window.crypto && !window.crypto.randomUUID) {
  (window.crypto as any).randomUUID = (): string => {
    return 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'.replace(/x/g, () =>
      (Math.random() * 16 | 0).toString(16)
    );
  };
}

// monaco-editor 0.55+ 不再需要预设 MonacoEnvironment.getWorkerUrl：
// editor.main.js 会自动设置 self.MonacoEnvironment

platformBrowserDynamic().bootstrapModule(AppModule)
  .catch(err => console.error(err));

