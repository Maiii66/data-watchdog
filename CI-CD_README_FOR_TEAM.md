# CI/CD README for Team - Data Watchdog

## What is CI/CD?

CI/CD (Continuous Integration/Continuous Deployment) automatically tests your code, checks quality, builds Docker images, and notifies the team every time you push to GitHub. This ensures the codebase is always in a working state.

---

## How to Use It

### 1. Write Code
Make your changes to any Python file.

### 2. Commit and Push
```bash
git add .
git commit -m "Description of changes"
git push origin main
```

### 3. Check Results
- Go to GitHub > Actions tab
- Green checkmark = All tests passed
- Red X = Something needs fixing

---

## What Happens Automatically

When you push code:

1. **Tests run** - pytest checks all functionality
2. **Linting runs** - flake8 checks code style
3. **Docker builds** - Production image is created
4. **Notifications sent** - Team gets Slack and Gmail alerts

---

## If Tests Fail

1. Go to GitHub > Actions tab
2. Click on the failed run
3. Scroll to see which test failed
4. Fix the issue locally
5. Commit and push again

---

## Adding New Tests

Add test functions to `tests/test_basic.py`:

```python
def test_my_new_feature():
    """Test description."""
    result = my_function()
    assert result == expected_value
```

The CI/CD pipeline will automatically run new tests on next push.

---

## Quick Reference

| Command | Purpose |
|---|---|
| `pytest tests/ -v` | Run tests locally |
| `flake8 .` | Check code style |
| `docker build -f Dockerfile.prod -t data-watchdog .` | Build Docker image |
| `docker-compose -f docker-compose.test.yml up` | Run tests in Docker |

---

## Important Notes

- **Never commit secrets** - Use GitHub Secrets for sensitive data
- **Always run tests locally** before pushing
- **Keep tests fast** - Each test should complete in <5 seconds
- **Use descriptive test names** - Other developers should understand what's tested

---

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Docker Documentation](https://docs.docker.com/)
- [flake8 Documentation](https://flake8.pycqa.org/)

---

## Support

For questions or issues:
1. Check this document first
2. Review CI-CD_SETUP_GUIDE.md for detailed instructions
3. Look at GitHub Actions logs for error details
4. Ask the team in #dev channel
