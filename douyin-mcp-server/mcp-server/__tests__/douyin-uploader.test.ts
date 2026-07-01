import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock fs/promises with hoisted factory
vi.mock('fs/promises', () => {
  return {
    default: {
      readFile: vi.fn(),
      writeFile: vi.fn(),
      stat: vi.fn(),
      unlink: vi.fn(),
      rm: vi.fn(),
    },
    readFile: vi.fn(),
    writeFile: vi.fn(),
    stat: vi.fn(),
    unlink: vi.fn(),
    rm: vi.fn(),
  };
});

// Mock puppeteer
vi.mock('puppeteer', () => ({
  default: {
    launch: vi.fn(),
  },
}));

// Import after mocks are set up
import { DouyinUploader } from '../douyin-uploader.js';
import fs from 'fs/promises';

describe('DouyinUploader', () => {
  let uploader: DouyinUploader;

  beforeEach(() => {
    uploader = new DouyinUploader();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getCookiesInfo', () => {
    it('should return exists: false when cookies file does not exist', async () => {
      vi.mocked(fs.readFile).mockRejectedValue(new Error('ENOENT'));

      const result = await uploader.getCookiesInfo();

      expect(result).toEqual({ exists: false });
    });

    it('should return cookie info when cookies file exists', async () => {
      const mockCookies = [{ name: 'test', value: 'value' }];
      const mockStats = { mtime: new Date('2024-01-01') };

      vi.mocked(fs.readFile).mockResolvedValue(JSON.stringify(mockCookies));
      vi.mocked(fs.stat).mockResolvedValue(mockStats as any);

      const result = await uploader.getCookiesInfo();

      expect(result.exists).toBe(true);
      expect(result.count).toBe(1);
      expect(result.created).toBeDefined();
    });

    it('should handle invalid JSON in cookies file', async () => {
      vi.mocked(fs.readFile).mockResolvedValue('invalid json');

      const result = await uploader.getCookiesInfo();

      expect(result).toEqual({ exists: false });
    });
  });

  describe('clearData', () => {
    it('should not throw when files do not exist', async () => {
      const enoentError = new Error('ENOENT') as NodeJS.ErrnoException;
      enoentError.code = 'ENOENT';

      vi.mocked(fs.unlink).mockRejectedValue(enoentError);
      vi.mocked(fs.rm).mockRejectedValue(enoentError);

      await expect(uploader.clearData()).resolves.not.toThrow();
    });

    it('should call unlink and rm with correct paths', async () => {
      vi.mocked(fs.unlink).mockResolvedValue(undefined);
      vi.mocked(fs.rm).mockResolvedValue(undefined);

      await uploader.clearData();

      expect(fs.unlink).toHaveBeenCalled();
      expect(fs.rm).toHaveBeenCalledWith(
        expect.stringContaining('chrome-user-data'),
        { recursive: true, force: true }
      );
    });
  });

  describe('checkLogin', () => {
    it('should return isValid: false when cookies file is empty', async () => {
      vi.mocked(fs.readFile).mockResolvedValue('[]');

      const result = await uploader.checkLogin();

      expect(result).toEqual({ isValid: false });
    });

    it('should return isValid: false when cookies file does not exist', async () => {
      vi.mocked(fs.readFile).mockRejectedValue(new Error('ENOENT'));

      const result = await uploader.checkLogin();

      expect(result).toEqual({ isValid: false });
    });
  });

  describe('uploadVideo', () => {
    it('should return error when video file does not exist', async () => {
      vi.mocked(fs.stat).mockRejectedValue(new Error('ENOENT'));

      const result = await uploader.uploadVideo({
        videoPath: '/nonexistent/video.mp4',
        title: 'Test Video',
      });

      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    it('should return error when cookies are not found', async () => {
      vi.mocked(fs.stat).mockResolvedValue({ isFile: () => true, size: 1000 } as any);
      vi.mocked(fs.readFile).mockRejectedValue(new Error('ENOENT'));

      const result = await uploader.uploadVideo({
        videoPath: '/path/to/video.mp4',
        title: 'Test Video',
      });

      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    it('should return error when cookies array is empty', async () => {
      vi.mocked(fs.stat).mockResolvedValue({ isFile: () => true, size: 1000 } as any);
      vi.mocked(fs.readFile).mockResolvedValue('[]');

      const result = await uploader.uploadVideo({
        videoPath: '/path/to/video.mp4',
        title: 'Test Video',
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('No login cookies found');
    });
  });
});
