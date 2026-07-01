import { describe, it, expect } from 'vitest';
import { CONFIG } from '../douyin-uploader.js';

describe('CONFIG', () => {
  describe('TIMEOUTS', () => {
    it('should have all required timeout values defined', () => {
      expect(CONFIG.TIMEOUTS.LOGIN_POLL_INTERVAL).toBeDefined();
      expect(CONFIG.TIMEOUTS.COOKIE_VALIDATION_WAIT).toBeDefined();
      expect(CONFIG.TIMEOUTS.PAGE_LOAD_WAIT).toBeDefined();
      expect(CONFIG.TIMEOUTS.MIN_UPLOAD_WAIT).toBeDefined();
      expect(CONFIG.TIMEOUTS.FORM_SUBMIT_WAIT).toBeDefined();
      expect(CONFIG.TIMEOUTS.PUBLISH_WAIT).toBeDefined();
      expect(CONFIG.TIMEOUTS.NAVIGATION_TIMEOUT).toBeDefined();
      expect(CONFIG.TIMEOUTS.FILE_INPUT_TIMEOUT).toBeDefined();
      expect(CONFIG.TIMEOUTS.TITLE_INPUT_TIMEOUT).toBeDefined();
    });

    it('should have reasonable timeout values', () => {
      // 所有超时应为正数
      Object.values(CONFIG.TIMEOUTS).forEach((value) => {
        expect(value).toBeGreaterThan(0);
      });

      // 导航超时应该足够长
      expect(CONFIG.TIMEOUTS.NAVIGATION_TIMEOUT).toBeGreaterThanOrEqual(30000);

      // 轮询间隔不应太短（避免频繁请求）
      expect(CONFIG.TIMEOUTS.LOGIN_POLL_INTERVAL).toBeGreaterThanOrEqual(1000);
    });
  });

  describe('UPLOAD_WAIT_MULTIPLIER', () => {
    it('should be a positive number', () => {
      expect(CONFIG.UPLOAD_WAIT_MULTIPLIER).toBeGreaterThan(0);
    });

    it('should calculate reasonable wait times for different file sizes', () => {
      const smallFile = 1 * 1024 * 1024; // 1MB
      const largeFile = 100 * 1024 * 1024; // 100MB

      const smallFileWait = Math.max(
        CONFIG.TIMEOUTS.MIN_UPLOAD_WAIT,
        smallFile / CONFIG.UPLOAD_WAIT_MULTIPLIER
      );
      const largeFileWait = Math.max(
        CONFIG.TIMEOUTS.MIN_UPLOAD_WAIT,
        largeFile / CONFIG.UPLOAD_WAIT_MULTIPLIER
      );

      // 小文件应使用最小等待时间
      expect(smallFileWait).toBe(CONFIG.TIMEOUTS.MIN_UPLOAD_WAIT);

      // 大文件等待时间应更长
      expect(largeFileWait).toBeGreaterThan(CONFIG.TIMEOUTS.MIN_UPLOAD_WAIT);
    });
  });
});
