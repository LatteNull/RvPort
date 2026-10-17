import { ActivatedRouteSnapshot, DetachedRouteHandle, RouteReuseStrategy } from '@angular/router';

export class CustomReuseStrategy implements RouteReuseStrategy {

    // 控制是否缓存组件（这里返回 false，表示不缓存）
    shouldDetach(route: ActivatedRouteSnapshot): boolean {
        return false;
    }

    // 组件缓存如何存储（我们不缓存，直接空实现）
    store(route: ActivatedRouteSnapshot, handle: DetachedRouteHandle | null): void {}

    // 是否允许从缓存恢复（不允许）
    shouldAttach(route: ActivatedRouteSnapshot): boolean {
        return false;
    }

    // 从缓存中恢复组件（返回 null，表示没有缓存）
    retrieve(route: ActivatedRouteSnapshot): DetachedRouteHandle | null {
        return null;
    }

    // 是否复用路由（false 表示每次都重新加载组件）
    shouldReuseRoute(future: ActivatedRouteSnapshot, curr: ActivatedRouteSnapshot): boolean {
        const reuse = future.data['reuse'];
        if (reuse === false) {
          return false;
        }
        return future.routeConfig === curr.routeConfig;
    }

}
