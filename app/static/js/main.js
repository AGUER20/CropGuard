// CropGuard — small UX helpers (no framework needed).
document.addEventListener("DOMContentLoaded", function () {
  // Animate confidence bars from 0 -> target width.
  document.querySelectorAll(".cg-confidence-fill").forEach(function (el) {
    var target = el.getAttribute("data-width") || "0%";
    requestAnimationFrame(function () {
      el.style.width = target;
    });
  });

  // Live filename preview + image preview on the upload dropzone.
  var input = document.getElementById("leaf_image");
  var preview = document.getElementById("image-preview");
  var dropzoneText = document.getElementById("dropzone-text");
  if (input) {
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) {
        var reader = new FileReader();
        reader.onload = function (e) {
          if (preview) {
            preview.src = e.target.result;
            preview.classList.remove("d-none");
          }
        };
        reader.readAsDataURL(input.files[0]);
        if (dropzoneText) dropzoneText.textContent = input.files[0].name;
      }
    });
  }

  // Star rating widget: clicking a star sets the hidden numeric input.
  document.querySelectorAll(".cg-star-input").forEach(function (wrap) {
    var hidden = wrap.querySelector("input[type=hidden], input[type=number]");
    var stars = wrap.querySelectorAll(".cg-star-btn");
    stars.forEach(function (star, idx) {
      star.addEventListener("click", function (e) {
        e.preventDefault();
        hidden.value = idx + 1;
        stars.forEach(function (s, i) {
          s.classList.toggle("bi-star-fill", i <= idx);
          s.classList.toggle("bi-star", i > idx);
        });
      });
    });
  });
});
