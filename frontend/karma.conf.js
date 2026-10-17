module.exports = function(config) {
    config.set({
      captureConsole: true, // 允许捕获控制台日志
      logLevel: config.LOG_INFO, // 让 Karma 输出 `console.log`

      // 其他配置项
      browsers: ['ChromeHeadless'],
      frameworks: ['jasmine'],
      reporters: ['progress', 'kjhtml'],
    });
};
