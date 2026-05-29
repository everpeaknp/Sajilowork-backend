(function () {
  function initEditors() {
    if (typeof tinymce === 'undefined') {
      return;
    }
    document.querySelectorAll('textarea.tinymce-editor').forEach(function (el) {
      if (!el.id) {
        el.id = 'tinymce-' + Math.random().toString(36).slice(2, 10);
      }
      if (tinymce.get(el.id)) {
        return;
      }
      tinymce.init({
        target: el,
        height: 520,
        menubar: 'edit view insert format tools table help',
        plugins:
          'advlist autolink lists link image charmap preview anchor searchreplace visualblocks code fullscreen insertdatetime media table help wordcount',
        toolbar:
          'undo redo | blocks | bold italic underline strikethrough | alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | link image media table | removeformat code fullscreen',
        content_style:
          'body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; font-size: 15px; line-height: 1.6; color: #0b1442; }',
        promotion: false,
        branding: false,
        relative_urls: false,
        convert_urls: true,
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEditors);
  } else {
    initEditors();
  }
})();
